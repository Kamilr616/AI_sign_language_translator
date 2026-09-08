"""Lay the window's cards out on a 16:9 canvas, one screen at a time.

The window is a board: a fixed 1920x1080 canvas scaled to the window, with no
scrolling. The cards (camera, text bar, transcript, results, settings, author)
sit in three columns, and which of them are shown depends on the screen and
on the user's view toggles:

- ``live``: the camera as large as possible with the results; the text bar
  floats over the bottom of the preview like subtitles,
- ``studio``: every card the user has switched on,
- ``settings``: the settings and author cards next to a large camera preview.

A hidden card gives its space away: without the results column the camera
column widens, without the transcript the camera grows down, and hiding the
header hands its strip to the cards. Only the camera, text and transcript
cards are resized; the others keep the size they were designed with in
``gui.ui`` and are only placed.

Pure geometry, no Qt dependency: ``compute_layout`` returns rectangles.
"""

CANVAS = (1920, 1080)
MARGIN = 40
GAP = 24
HEADER_HEIGHT = 80

RESULTS_WIDTH = 480
SETTINGS_WIDTH = 512
SETTINGS_HEIGHT = 616
AUTHOR_HEIGHT = 280
AUTHOR_MIN_HEIGHT = 160
TEXT_HEIGHT = 96
TRANSCRIPT_MIN_HEIGHT = 150
# Inset of the text bar when it floats over the camera preview (live screen).
OVERLAY_INSET = 24
# Space a card's frame takes around its content: side padding and the title strip.
CARD_SIDE = 16
CARD_TOP = 36
CARD_BOTTOM = 16
# Aspect ratio of the camera preview; frames are scaled to 640x480.
PREVIEW_RATIO = (4, 3)

SCREENS = ('live', 'studio', 'settings')
CARDS = ('camera', 'text', 'transcript', 'results', 'settings', 'author')
# Cards the user may switch on and off from the view menu.
TOGGLABLE = ('text', 'transcript', 'results', 'settings', 'author')


def cards_on_screen(screen, toggles):
    """
    The cards a screen shows, given the user's toggles (a ``{card: bool}``
    mapping; a missing card counts as switched on).

    Args:
        screen (str): One of SCREENS.
        toggles (dict): Which togglable cards the user wants to see.

    Returns:
        set: Names from CARDS.
    """
    if screen not in SCREENS:
        raise ValueError(f"Unknown screen: {screen}")
    wanted = {card for card in CARDS if card == 'camera' or toggles.get(card, True)}
    if screen == 'live':
        return wanted & {'camera', 'text', 'results'}
    if screen == 'settings':
        return (wanted & {'author'}) | {'camera', 'settings'}
    return wanted


def text_overlaid(screen):
    """True when the text bar floats over the camera preview on this screen."""
    return screen == 'live'


def preview_rect(card):
    """The largest 4:3 rectangle centred in a camera card's content area."""
    x, y, width, height = card
    inner_w = width - 2 * CARD_SIDE
    inner_h = height - CARD_TOP - CARD_BOTTOM
    ratio_w, ratio_h = PREVIEW_RATIO
    if inner_w * ratio_h <= inner_h * ratio_w:
        preview_w = inner_w
        preview_h = inner_w * ratio_h // ratio_w
    else:
        preview_h = inner_h
        preview_w = inner_h * ratio_w // ratio_h
    return (
        x + CARD_SIDE + (inner_w - preview_w) // 2,
        y + CARD_TOP + (inner_h - preview_h) // 2,
        preview_w,
        preview_h,
    )


def compute_layout(screen, toggles, header_visible=True, canvas=CANVAS):
    """
    Place the cards of a screen on the canvas.

    Returns:
        dict: ``{card: (x, y, width, height)}`` for every name in CARDS; a
              hidden card maps to None.
    """
    shown = cards_on_screen(screen, toggles)
    canvas_w, canvas_h = canvas
    top = MARGIN + (HEADER_HEIGHT if header_visible else 0)
    left = MARGIN
    width = canvas_w - 2 * MARGIN
    height = canvas_h - top - MARGIN
    layout = {card: None for card in CARDS}

    right_column = 'settings' in shown or 'author' in shown
    middle_column = 'results' in shown
    left_width = width
    if right_column:
        left_width -= SETTINGS_WIDTH + GAP
    if middle_column:
        left_width -= RESULTS_WIDTH + GAP

    # Left column: camera, then the text bar, then the transcript. On the live
    # screen the text bar floats over the preview instead of taking a row.
    overlay = text_overlaid(screen) and 'text' in shown
    stacked = ('text' in shown and not overlay) or 'transcript' in shown
    remaining = height
    if 'text' in shown and not overlay:
        remaining -= TEXT_HEIGHT + GAP
    if 'transcript' in shown:
        remaining -= TRANSCRIPT_MIN_HEIGHT + GAP
    ratio_w, ratio_h = PREVIEW_RATIO
    natural = (left_width - 2 * CARD_SIDE) * ratio_h // ratio_w + CARD_TOP + CARD_BOTTOM
    camera_h = min(remaining, natural) if stacked else height
    y = top
    layout['camera'] = (left, y, left_width, camera_h)
    y += camera_h + GAP
    if overlay:
        layout['text'] = (
            left + OVERLAY_INSET, top + height - TEXT_HEIGHT - OVERLAY_INSET,
            left_width - 2 * OVERLAY_INSET, TEXT_HEIGHT,
        )
    elif 'text' in shown:
        layout['text'] = (left, y, left_width, TEXT_HEIGHT)
        y += TEXT_HEIGHT + GAP
    if 'transcript' in shown:
        layout['transcript'] = (left, y, left_width, top + height - y)

    # Middle column: the results card takes the full height.
    x = left + left_width + GAP
    if middle_column:
        layout['results'] = (x, top, RESULTS_WIDTH, height)
        x += RESULTS_WIDTH + GAP

    # Right column: settings, then the author card in what is left.
    if right_column:
        y = top
        if 'settings' in shown:
            layout['settings'] = (x, y, SETTINGS_WIDTH, SETTINGS_HEIGHT)
            y += SETTINGS_HEIGHT + GAP
        if 'author' in shown:
            author_h = min(AUTHOR_HEIGHT, top + height - y) if 'settings' in shown else height
            if author_h >= AUTHOR_MIN_HEIGHT:
                layout['author'] = (x, y, SETTINGS_WIDTH, author_h)
    return layout
