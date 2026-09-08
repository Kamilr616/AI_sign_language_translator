import threading

from camera import CameraApp


class FakeCapture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return not self.released

    def release(self):
        self.released = True


def test_destroy_is_safe_when_called_more_than_once():
    camera = CameraApp.__new__(CameraApp)
    camera._lock = threading.Lock()
    camera.cap = FakeCapture()

    camera.destroy()
    camera.destroy()

    assert camera.is_closed()
