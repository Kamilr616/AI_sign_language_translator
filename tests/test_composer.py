from composer import TextComposer


def feed(composer, sign, frames):
    return [composer.feed(sign) for _ in range(frames)]


def test_a_letter_is_written_once_when_stable():
    composer = TextComposer(stable_frames=3)

    events = feed(composer, 'A', 10)

    assert composer.text == 'A'
    assert events == [None, None, 'A'] + [None] * 7


def test_a_flicker_is_not_written():
    composer = TextComposer(stable_frames=3)

    feed(composer, 'A', 3)
    feed(composer, 'B', 1)
    feed(composer, 'A', 3)
    feed(composer, 'C', 2)
    feed(composer, 'B', 3)

    assert composer.text == 'AB'


def test_the_same_letter_is_written_again_after_a_short_rest():
    composer = TextComposer(stable_frames=3, rest_frames=30)

    feed(composer, 'L', 3)
    feed(composer, '', 5)
    feed(composer, 'L', 3)

    assert composer.text == 'LL'


def test_a_long_rest_ends_the_word_with_a_single_space():
    composer = TextComposer(stable_frames=3, rest_frames=30)

    feed(composer, 'H', 3)
    feed(composer, 'I', 3)
    events = feed(composer, '', 90)
    feed(composer, 'U', 3)

    assert composer.text == 'HI U'
    assert events.count(' ') == 1


def test_no_space_before_the_first_letter():
    composer = TextComposer(stable_frames=3, rest_frames=30)

    feed(composer, '', 60)
    feed(composer, 'A', 3)

    assert composer.text == 'A'


def test_space_and_del_classes_edit_the_text():
    composer = TextComposer(stable_frames=3)

    feed(composer, 'A', 3)
    feed(composer, 'B', 3)
    assert feed(composer, 'del', 3)[-1] == 'del'
    assert composer.text == 'A'
    feed(composer, 'space', 3)
    feed(composer, '', 3)
    feed(composer, 'space', 3)
    assert composer.text == 'A '
    feed(composer, 'del', 3)
    feed(composer, '', 3)
    feed(composer, 'del', 3)
    feed(composer, '', 3)
    assert feed(composer, 'del', 3)[-1] is None

    assert composer.text == ''


def test_holding_del_deletes_only_once():
    composer = TextComposer(stable_frames=3)

    feed(composer, 'A', 3)
    feed(composer, 'B', 3)
    feed(composer, 'C', 3)
    feed(composer, 'del', 12)

    assert composer.text == 'AB'


def test_text_keeps_only_the_newest_characters():
    composer = TextComposer(stable_frames=1, max_length=4)

    for letter in 'ABCDEFG':
        composer.feed(letter)

    assert composer.text == 'DEFG'


def test_clear_forgets_text_and_candidate():
    composer = TextComposer(stable_frames=3)

    feed(composer, 'A', 3)
    composer.clear()
    feed(composer, 'A', 2)
    assert composer.text == ''
    feed(composer, 'A', 1)

    assert composer.text == 'A'
