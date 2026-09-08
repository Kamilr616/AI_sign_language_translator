import pytest

import corrector
from corrector import WordCorrector, weighted_distance


def make_corrector():
    return WordCorrector.from_words({
        'hello': 1000, 'help': 5000, 'world': 800, 'wold': 5, 'thank': 600, 'you': 9000,
        'name': 100, 'none': 5000, 'nine': 100, 'the': 20000, 'ok': 300, 'see': 700,
        'call': 400, 'called': 9000, 'me': 8000, 'good': 500, 'morning': 200, 'a': 30000,
        'i': 25000, 'am': 4000, 'here': 3000, 'nan': 50, 'e': 40,
    })


def test_a_known_word_is_kept():
    assert make_corrector().correct('HELLO') == 'HELLO'
    assert make_corrector().correct('world') == 'world'


def test_an_unknown_word_becomes_the_closest_known_one_keeping_its_case():
    assert make_corrector().correct('HELLLO') == 'HELLO'
    assert make_corrector().correct('wrold') == 'world'
    assert make_corrector().correct('THAMK') == 'THANK'


def test_a_doubled_letter_beats_a_more_frequent_full_edit():
    assert make_corrector().correct('HELO') == 'HELLO'


def test_confusable_hand_shapes_beat_frequency():
    assert make_corrector().correct('NANE') == 'NAME'
    assert make_corrector().correct('YOV') == 'YOU'


def test_the_more_frequent_candidate_wins_at_equal_weighted_distance():
    assert make_corrector().correct('WROLD') == 'WORLD'


def test_short_words_are_corrected_by_one_edit_only():
    assert make_corrector().correct('NAME') == 'NAME'
    assert make_corrector().correct('NXXE') == 'NXXE'


def test_words_shorter_than_three_letters_and_non_letters_are_left_alone():
    assert make_corrector().correct('OK') == 'OK'
    assert make_corrector().correct('YU') == 'YU'
    assert make_corrector().correct('A') == 'A'
    assert make_corrector().correct('') == ''
    assert make_corrector().correct('HEL0') == 'HEL0'


def test_run_together_words_are_split_when_no_correction_is_in_reach():
    assert make_corrector().correct('HELLOYOU') == 'HELLO YOU'
    assert make_corrector().correct('goodmorning') == 'good morning'
    assert make_corrector().correct('IAMHERE') == 'I AM HERE'


def test_splitting_wins_over_a_more_expensive_correction():
    assert make_corrector().correct('CALLME') == 'CALL ME'


def test_a_cheap_correction_wins_over_splitting():
    assert make_corrector().correct('HELLLO') == 'HELLO'


def test_words_are_not_split_into_unknown_or_single_letter_pieces():
    assert make_corrector().correct('HELLOXQZ') == 'HELLOXQZ'
    assert make_corrector().correct('NANEXQ') == 'NANEXQ'
    assert make_corrector().correct('SEEYOUXQ') == 'SEEYOUXQ'


def test_weighted_distance_costs():
    assert weighted_distance('hello', 'hello') == 0.0
    assert weighted_distance('helo', 'hello') == pytest.approx(0.5)
    assert weighted_distance('helllo', 'hello') == pytest.approx(0.5)
    assert weighted_distance('helo', 'help') == pytest.approx(1.0)
    assert weighted_distance('nane', 'name') == pytest.approx(0.5)
    assert weighted_distance('nane', 'none') == pytest.approx(1.0)
    assert weighted_distance('wrold', 'world') == pytest.approx(1.0)
    assert weighted_distance('yov', 'you') == pytest.approx(0.5)
    assert weighted_distance('abc', 'xyz') == pytest.approx(3.0)


def test_nothing_is_corrected_before_the_dictionary_is_loaded():
    fresh = WordCorrector()

    assert fresh.ready is False
    assert fresh.correct('HELLLO') == 'HELLLO'


def test_the_bundled_english_dictionary_loads():
    fresh = WordCorrector()

    assert fresh.load() is True
    assert fresh.ready is True
    assert fresh.correct('HELO') == 'HELLO'
    assert fresh.correct('WROLD') == 'WORLD'
    assert fresh.correct('PLEESE') == 'PLEASE'
    assert fresh.correct('YOU') == 'YOU'
    assert fresh.correct('THANKYOU') == 'THANK YOU'
    assert fresh.correct('WHEREAREYOU') == 'WHERE ARE YOU'
    assert fresh.correct('XQZVW') == 'XQZVW'


def test_a_missing_dictionary_file_is_reported_not_raised(tmp_path):
    fresh = WordCorrector()

    assert fresh.load(tmp_path / 'missing.txt') is False
    assert fresh.ready is False
    assert fresh.correct('HELLLO') == 'HELLLO'


def test_load_async_loads_once_in_the_background():
    fresh = WordCorrector()

    fresh.load_async()
    first_thread = fresh._thread
    fresh.load_async()
    first_thread.join(timeout=30)

    assert fresh._thread is first_thread
    assert fresh.ready is True


def test_without_symspellpy_words_pass_through(monkeypatch):
    monkeypatch.setattr(corrector, 'SymSpell', None)
    fresh = WordCorrector()

    assert fresh.load() is False
    assert WordCorrector.from_words({'hello': 1}).correct('HELLLO') == 'HELLLO'


def test_completions_start_with_the_prefix_most_frequent_first():
    assert make_corrector().complete('HE') == ['help', 'here', 'hello']
    assert make_corrector().complete('hel') == ['help', 'hello']
    assert make_corrector().complete('WORL') == ['world']


def test_completions_need_two_letters_and_a_loaded_dictionary():
    assert make_corrector().complete('H') == []
    assert make_corrector().complete('') == []
    assert make_corrector().complete('H3') == []
    assert make_corrector().complete('XQ') == []
    assert WordCorrector().complete('HE') == []


def test_the_bundled_dictionary_completes_common_prefixes():
    fresh = WordCorrector()
    fresh.load()

    completions = fresh.complete('THAN')

    assert completions[0] == 'than'
    assert 'thank' in completions or 'thanks' in completions
    assert len(completions) == 3
