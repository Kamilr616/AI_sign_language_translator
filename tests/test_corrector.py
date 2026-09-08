import corrector
from corrector import WordCorrector


def make_corrector():
    return WordCorrector.from_words({
        'hello': 1000, 'help': 5000, 'world': 800, 'thank': 600, 'you': 9000,
        'name': 700, 'nine': 100, 'the': 20000, 'ok': 300,
    })


def test_a_known_word_is_kept():
    assert make_corrector().correct('HELLO') == 'HELLO'
    assert make_corrector().correct('world') == 'world'


def test_an_unknown_word_becomes_the_closest_known_one_keeping_its_case():
    assert make_corrector().correct('HELLLO') == 'HELLO'
    assert make_corrector().correct('wrold') == 'world'
    assert make_corrector().correct('THAMK') == 'THANK'


def test_the_more_frequent_candidate_wins_at_equal_distance():
    assert make_corrector().correct('HELO') == 'HELP'


def test_short_words_are_corrected_by_one_edit_only():
    assert make_corrector().correct('NAME') == 'NAME'
    assert make_corrector().correct('NANE') == 'NAME'
    assert make_corrector().correct('NXXE') == 'NXXE'


def test_words_shorter_than_three_letters_and_non_letters_are_left_alone():
    assert make_corrector().correct('OK') == 'OK'
    assert make_corrector().correct('YU') == 'YU'
    assert make_corrector().correct('A') == 'A'
    assert make_corrector().correct('') == ''
    assert make_corrector().correct('HEL0') == 'HEL0'


def test_nothing_is_corrected_before_the_dictionary_is_loaded():
    fresh = WordCorrector()

    assert fresh.ready is False
    assert fresh.correct('HELLLO') == 'HELLLO'


def test_the_bundled_english_dictionary_loads():
    fresh = WordCorrector()

    assert fresh.load() is True
    assert fresh.ready is True
    assert fresh.correct('WROLD') == 'WORLD'
    assert fresh.correct('PLEESE') == 'PLEASE'
    assert fresh.correct('YOU') == 'YOU'


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
