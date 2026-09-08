import pytest

import board
from board import CANVAS, CARDS, MARGIN, cards_on_screen, compute_layout, preview_rect


ALL_ON = {card: True for card in board.TOGGLABLE}


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def visible(layout):
    return {card: rect for card, rect in layout.items() if rect is not None}


@pytest.mark.parametrize('screen', board.SCREENS)
@pytest.mark.parametrize('header', [True, False])
def test_cards_fit_the_canvas_without_overlapping(screen, header):
    layout = compute_layout(screen, ALL_ON, header_visible=header)
    rects = visible(layout)
    width, height = CANVAS

    for rect in rects.values():
        x, y, w, h = rect
        assert x >= MARGIN and y >= MARGIN
        assert x + w <= width - MARGIN and y + h <= height - MARGIN
    names = list(rects)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            if {first, second} == {'camera', 'text'} and board.text_overlaid(screen):
                continue
            assert not overlaps(rects[first], rects[second]), (first, second)


def test_on_the_live_screen_the_text_bar_floats_over_a_full_height_preview():
    layout = compute_layout('live', ALL_ON)
    cx, cy, cw, ch = layout['camera']
    tx, ty, tw, th = layout['text']

    assert board.text_overlaid('live') and not board.text_overlaid('studio')
    assert ch == CANVAS[1] - 2 * MARGIN - board.HEADER_HEIGHT
    assert tx > cx and ty > cy and tx + tw < cx + cw and ty + th < cy + ch
    assert ty + th == cy + ch - board.OVERLAY_INSET


def test_the_studio_screen_shows_every_card_and_the_live_screen_only_the_outputs():
    assert cards_on_screen('studio', ALL_ON) == set(CARDS)
    assert cards_on_screen('live', ALL_ON) == {'camera', 'text', 'results'}
    assert cards_on_screen('settings', ALL_ON) == {'camera', 'settings', 'author'}


def test_toggles_remove_cards_but_never_the_camera():
    nothing = {card: False for card in board.TOGGLABLE}

    assert cards_on_screen('studio', nothing) == {'camera'}
    assert cards_on_screen('live', nothing) == {'camera'}
    assert cards_on_screen('settings', nothing) == {'camera', 'settings'}
    with pytest.raises(ValueError):
        cards_on_screen('gallery', ALL_ON)


def test_hidden_cards_give_their_space_to_the_camera():
    studio = compute_layout('studio', ALL_ON)
    no_transcript = compute_layout('studio', {**ALL_ON, 'transcript': False})
    no_columns = compute_layout('studio', {**ALL_ON, 'results': False, 'settings': False, 'author': False})
    alone = compute_layout('studio', {card: False for card in board.TOGGLABLE})

    assert no_transcript['transcript'] is None
    assert no_transcript['camera'][3] > studio['camera'][3]
    assert no_columns['camera'][2] > studio['camera'][2]
    assert alone['camera'] == (MARGIN, MARGIN + board.HEADER_HEIGHT, CANVAS[0] - 2 * MARGIN, CANVAS[1] - 2 * MARGIN - board.HEADER_HEIGHT)


def test_hiding_the_header_moves_the_cards_up():
    with_header = compute_layout('live', ALL_ON, header_visible=True)
    without = compute_layout('live', ALL_ON, header_visible=False)

    assert without['camera'][1] == MARGIN
    assert with_header['camera'][1] == MARGIN + board.HEADER_HEIGHT
    assert without['results'][3] == with_header['results'][3] + board.HEADER_HEIGHT


def test_the_preview_keeps_four_to_three_inside_its_card():
    for screen in board.SCREENS:
        camera = compute_layout(screen, ALL_ON)['camera']
        x, y, w, h = preview_rect(camera)

        assert abs(w * 3 - h * 4) <= 4
        assert x >= camera[0] + board.CARD_SIDE and y >= camera[1] + board.CARD_TOP
        assert x + w <= camera[0] + camera[2] - board.CARD_SIDE
        assert y + h <= camera[1] + camera[3] - board.CARD_BOTTOM


def test_the_author_card_is_dropped_when_there_is_no_room_for_it():
    layout = compute_layout('settings', ALL_ON, canvas=(1920, 900))

    assert layout['settings'] is not None
    assert layout['author'] is None
