"""Correct fingerspelled words against an English word list.

Fingerspelling recognition confuses similar hand shapes (M/N, U/V, A/S/T) and
drops or doubles letters when the hand moves. ``WordCorrector`` matches every
finished word against SymSpell's frequency dictionary of 82 765 English words
(bundled with the ``symspellpy`` package, MIT licensed) and replaces an unknown
word with the closest known one, preferring the more frequent candidate.

The dictionary takes about a second to load, so ``load_async()`` builds it on a
daemon thread; until it is ready, or when ``symspellpy`` is not installed,
``correct()`` returns every word unchanged.
"""

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


class WordCorrector:
    def __init__(self, max_edit_distance=2):
        """
        Args:
            max_edit_distance (int): Largest edit distance between a signed word and its correction.
        """
        self.max_edit_distance = max_edit_distance
        self._symspell = None
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
            corrector._symspell = symspell
            corrector._ready.set()
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

        self._symspell = symspell
        self._ready.set()
        logging.info("Word dictionary loaded: %d words", symspell.word_count)
        return True

    def _create_symspell(self):
        if SymSpell is None:
            logging.warning("symspellpy is not installed, words will not be corrected")
            return None
        return SymSpell(max_dictionary_edit_distance=self.max_edit_distance, prefix_length=7)

    def correct(self, word):
        """
        Return the closest dictionary word, or ``word`` itself when it is known,
        too short, not purely alphabetic, or the dictionary is not loaded.

        The case of the input is kept: an upper-case word gets an upper-case
        correction.
        """
        if not self.ready or not word or not word.isalpha() or len(word) < MIN_LENGTH:
            return word

        lowered = word.lower()
        distance = 1 if len(lowered) <= SHORT_WORD_LENGTH else self.max_edit_distance
        suggestions = self._symspell.lookup(
            lowered, Verbosity.CLOSEST, max_edit_distance=distance, include_unknown=True)
        best = suggestions[0].term
        if best == lowered:
            return word
        return best.upper() if word.isupper() else best
