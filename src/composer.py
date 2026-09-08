"""Assemble stable letters into words.

The composer receives the sign displayed on every frame (an empty string when
no sign is shown) and turns it into text the way a fingerspelling reader does:

- a letter is written once when it has been shown for ``stable_frames``
  consecutive frames; holding it longer does not repeat it,
- showing the same letter again after a short rest writes it again,
- resting the hand for ``rest_frames`` consecutive frames ends the word with a
  single space,
- the ``space`` and ``del`` classes of the 29-class models insert a space and
  delete the last character.

It has no Qt dependency, so it is unit-tested without a window.
"""

SPACE_SIGN = 'space'
DELETE_SIGN = 'del'


class TextComposer:
    def __init__(self, stable_frames=3, rest_frames=30, max_length=60):
        """
        Args:
            stable_frames (int): Consecutive frames a sign must be shown before it is written.
            rest_frames (int): Consecutive frames without a sign that end a word with a space.
            max_length (int): Oldest characters are dropped beyond this length.
        """
        self.stable_frames = stable_frames
        self.rest_frames = rest_frames
        self.max_length = max_length
        self.text = ''
        self._candidate = None
        self._stable = 0
        self._last_written = None
        self._rest = 0

    def clear(self):
        """Forget the text and the current candidate."""
        self.text = ''
        self._candidate = None
        self._stable = 0
        self._last_written = None
        self._rest = 0

    def feed(self, sign):
        """
        Account for one displayed frame.

        A sign is written on the frame it becomes stable, and only if it is not
        the sign written last: a one-frame flicker to another sign neither
        writes that sign nor re-arms the previous one. A stable rest (no sign
        for ``stable_frames``) or another stable sign re-arms it.

        Args:
            sign (str): The displayed sign, or an empty string for no sign.

        Returns:
            str or None: The letter that was just written, ' ' for a space,
                         'del' for a deletion, or None when nothing changed.
        """
        if sign != self._candidate:
            self._candidate = sign
            self._stable = 0
        self._stable += 1

        if not sign:
            self._rest += 1
            if self._stable == self.stable_frames:
                self._last_written = None
            if self._rest == self.rest_frames:
                return self._write(' ')
            return None
        self._rest = 0

        if self._stable != self.stable_frames or sign == self._last_written:
            return None
        self._last_written = sign
        return self._write(sign)

    def _write(self, token):
        if token == DELETE_SIGN:
            if not self.text:
                return None
            self.text = self.text[:-1]
            return DELETE_SIGN

        if token in (' ', SPACE_SIGN):
            if not self.text or self.text.endswith(' '):
                return None
            self.text += ' '
            return ' '

        self.text = (self.text + token)[-self.max_length:]
        return token
