"""Correct fingerspelled words against an English word list.

Fingerspelling recognition confuses similar hand shapes (M/N, U/V, A/S/T) and
drops or doubles letters when the hand moves. ``WordCorrector`` matches every
finished word against SymSpell's frequency dictionary of 82 765 English words
(bundled with the ``symspellpy`` package, MIT licensed) and replaces an unknown
word with the closest known one.

"Closest" is measured with a weighted Damerau-Levenshtein distance that knows
how fingerspelling fails: substituting one letter of a confusable hand-shape
group for another, doubling a letter or losing one of a doubled pair each cost
half an edit, every other edit costs one. Candidates at the same weighted
distance are ordered by frequency. A word that has no correction in reach is
split into known words when the hand did not rest between them (``helloyou``),
provided splitting is cheaper than the best single-word correction.

The dictionary takes about a second to load, so ``load_async()`` builds it on a
daemon thread; until it is ready, or when ``symspellpy`` is not installed,
``correct()`` returns every word unchanged.
"""

import bisect
import logging
import threading
from importlib import resources

try:
    from symspellpy import SymSpell, Verbosity
except ImportError:  # pragma: no cover - exercised only in a stale environment
    SymSpell = None
    Verbosity = None

DICTIONARY_PACKAGE = 'symspellpy'
DICTIONARY_FILE = 'frequency_dictionary_en_82_765.txt'
# Shorter words are left alone: almost any two letters are within one edit of
# a common word, so "correcting" them would only replace what was signed.
MIN_LENGTH = 3
# Words up to this length are corrected by a single edit only.
SHORT_WORD_LENGTH = 4
# Only words at least this long are tried as two or more run-together words.
MIN_SEGMENTATION_LENGTH = 6
# One-letter segments that are words on their own.
ONE_LETTER_WORDS = frozenset('ai')
# Completions are offered from this many letters on, and at most this many.
MIN_COMPLETION_PREFIX = 2
MAX_COMPLETIONS = 3
# Longest run of the sorted word list scanned for one prefix.
MAX_COMPLETION_SCAN = 4000
# Static ASL hand shapes that landmark classifiers mix up; a substitution
# inside a group costs CONFUSION_COST instead of a full edit.
CONFUSABLE_GROUPS = ('aemnst', 'uvrk', 'kp', 'ghq', 'co', 'dx', 'df', 'iyj', 'wf')
CONFUSION_COST = 0.5
DOUBLING_COST = 0.5


def _confusable_pairs(groups):
    pairs = set()
    for group in groups:
        for first in group:
            for second in group:
                if first != second:
                    pairs.add((first, second))
    return frozenset(pairs)


CONFUSABLE = _confusable_pairs(CONFUSABLE_GROUPS)


def _doubling_cost(text, index):
    """Cost of inserting or deleting ``text[index]``: half an edit when it doubles a neighbour."""
    letter = text[index]
    if (index > 0 and text[index - 1] == letter) or (index + 1 < len(text) and text[index + 1] == letter):
        return DOUBLING_COST
    return 1.0


def weighted_distance(signed, candidate):
    """
    Weighted optimal-string-alignment distance from the signed word to a candidate.

    Substituting confusable letters and doubling or de-doubling a letter cost
    half an edit; other substitutions, insertions, deletions and transpositions
    of adjacent letters cost one.
    """
    rows, cols = len(signed), len(candidate)
    table = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(1, rows + 1):
        table[i][0] = table[i - 1][0] + _doubling_cost(signed, i - 1)
    for j in range(1, cols + 1):
        table[0][j] = table[0][j - 1] + _doubling_cost(candidate, j - 1)

    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            a, b = signed[i - 1], candidate[j - 1]
            if a == b:
                substitution = 0.0
            elif (a, b) in CONFUSABLE:
                substitution = CONFUSION_COST
            else:
                substitution = 1.0
            best = min(
                table[i - 1][j] + _doubling_cost(signed, i - 1),
                table[i][j - 1] + _doubling_cost(candidate, j - 1),
                table[i - 1][j - 1] + substitution,
            )
            if i > 1 and j > 1 and a == candidate[j - 2] and signed[i - 2] == b:
                best = min(best, table[i - 2][j - 2] + 1.0)
            table[i][j] = best
    return table[rows][cols]


class WordCorrector:
    def __init__(self, max_edit_distance=2):
        """
        Args:
            max_edit_distance (int): Largest edit distance between a signed word and its correction.
        """
        self.max_edit_distance = max_edit_distance
        self._symspell = None
        self._sorted_words = []
        self._ready = threading.Event()
        self._thread = None

    @classmethod
    def from_words(cls, counts, max_edit_distance=2):
        """
        Build a ready corrector from a ``{word: frequency}`` mapping, for tests
        and for custom vocabularies.
        """
        corrector = cls(max_edit_distance=max_edit_distance)
        symspell = corrector._create_symspell()
        if symspell is not None:
            for word, count in counts.items():
                symspell.create_dictionary_entry(word.lower(), count)
            corrector._install(symspell)
        return corrector

    @property
    def ready(self):
        """True once a dictionary is loaded and corrections are available."""
        return self._ready.is_set()

    def load_async(self):
        """Load the bundled dictionary on a daemon thread; safe to call repeatedly."""
        if self.ready or (self._thread is not None and self._thread.is_alive()):
            return
        self._thread = threading.Thread(target=self.load, daemon=True, name="WordCorrectorLoader")
        self._thread.start()

    def load(self, path=None):
        """
        Load a SymSpell frequency dictionary (``term count`` per line).

        Args:
            path (str or Path): Dictionary file; the bundled English one by default.

        Returns:
            bool: True when the dictionary was loaded.
        """
        symspell = self._create_symspell()
        if symspell is None:
            return False

        try:
            if path is None:
                with resources.as_file(
                    resources.files(DICTIONARY_PACKAGE).joinpath(DICTIONARY_FILE)
                ) as bundled:
                    loaded = symspell.load_dictionary(str(bundled), term_index=0, count_index=1)
            else:
                loaded = symspell.load_dictionary(str(path), term_index=0, count_index=1)
        except Exception:
            logging.exception("Error while loading the word dictionary")
            return False

        if not loaded:
            logging.error("Word dictionary could not be read: %s", path or DICTIONARY_FILE)
            return False

        self._install(symspell)
        logging.info("Word dictionary loaded: %d words", symspell.word_count)
        return True

    def _install(self, symspell):
        """Publish a loaded dictionary together with its sorted word list."""
        self._sorted_words = sorted(symspell.words)
        self._symspell = symspell
        self._ready.set()

    def _create_symspell(self):
        if SymSpell is None:
            logging.warning("symspellpy is not installed, words will not be corrected")
            return None
        return SymSpell(max_dictionary_edit_distance=self.max_edit_distance, prefix_length=7)

    def correct(self, word):
        """
        Return the closest dictionary word (or words, when the signed word turns
        out to be several run together), or ``word`` itself when it is known,
        too short, not purely alphabetic, or the dictionary is not loaded.

        The case of the input is kept: an upper-case word gets an upper-case
        correction.
        """
        if not self.ready or not word or not word.isalpha() or len(word) < MIN_LENGTH:
            return word

        lowered = word.lower()
        if lowered in self._symspell.words:
            return word

        correction, correction_cost = self._closest_word(lowered)
        segmentation, segmentation_cost = self._split_words(lowered)
        if segmentation is not None and segmentation_cost < correction_cost:
            best = segmentation
        else:
            best = correction
        if best is None:
            return word
        return best.upper() if word.isupper() else best

    def complete(self, prefix, limit=MAX_COMPLETIONS):
        """
        Dictionary words starting with ``prefix`` (at least two letters), most
        frequent first; empty while the dictionary is not loaded.
        """
        if not self.ready or not prefix or not prefix.isalpha() or len(prefix) < MIN_COMPLETION_PREFIX:
            return []

        lowered = prefix.lower()
        words = self._sorted_words
        counts = self._symspell.words
        start = bisect.bisect_left(words, lowered)
        matches = []
        for word in words[start:start + MAX_COMPLETION_SCAN]:
            if not word.startswith(lowered):
                break
            matches.append(word)
        matches.sort(key=lambda word: -counts[word])
        return matches[:limit]

    def _closest_word(self, lowered):
        """The candidate with the lowest weighted distance, then the highest frequency."""
        distance = 1 if len(lowered) <= SHORT_WORD_LENGTH else self.max_edit_distance
        candidates = self._symspell.lookup(lowered, Verbosity.ALL, max_edit_distance=distance)
        if not candidates:
            return None, float('inf')
        ranked = min(
            candidates,
            key=lambda item: (weighted_distance(lowered, item.term), -item.count),
        )
        return ranked.term, weighted_distance(lowered, ranked.term)

    def _split_words(self, lowered):
        """Split a long unknown word into known ones; the cost is the number of splits."""
        if len(lowered) < MIN_SEGMENTATION_LENGTH:
            return None, float('inf')

        segments = self._symspell.word_segmentation(lowered, max_edit_distance=0).corrected_string.split(' ')
        if len(segments) < 2 or ''.join(segments) != lowered:
            return None, float('inf')
        for segment in segments:
            if segment not in self._symspell.words:
                return None, float('inf')
            if len(segment) == 1 and segment not in ONE_LETTER_WORDS:
                return None, float('inf')
        return ' '.join(segments), float(len(segments) - 1)
