import cv2
import time
import warnings
from PySide6.QtMultimedia import QMediaDevices


def count_available_cameras():
    """
    Sprawdza liczbę dostępnych kamer w systemie za pomocą Qt.

    Returns:
        int: Liczba dostępnych kamer.
    """
    cameras = QMediaDevices.videoInputs()
    return len(cameras)


class CameraApp:
    def __init__(self, **kwargs):
        """
        Initialize the AsyncCamera instance.

        Args:
            **kwargs: Additional keyword arguments to set camera properties.
        """

        try:
            self.cap = cv2.VideoCapture()
            self.open(kwargs["fd"])
        except Exception:
            warnings.warn("Error while opening the camera")
            self.destroy()
        finally:
            self.configure(**kwargs)

    def settings(self):
        if self.cap:
            self.cap.set(cv2.CAP_PROP_SETTINGS, 1)

    def configure(self, **kwargs):
        try:
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, kwargs["width"])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, kwargs["height"])
            # self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 50)
            # self.cap.set(cv2.CAP_PROP_CONTRAST, 50)
            # self.cap.set(cv2.CAP_PROP_SATURATION, 50)
            # self.cap.set(cv2.CAP_PROP_HUE, 0)
            # self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)
            #self.cap.set(cv2.CAP_PROP_SETTINGS, 1)
        except Exception:
            warnings.warn("Error while configuring the camera")
            self.destroy()

    def open(self, fd, direct_show=True):
        #CAP_DSHOW
        #CAP_MSMF
        #CAP_ANY
        if direct_show:
            camera_backend = cv2.CAP_DSHOW
        else:
            camera_backend = cv2.CAP_ANY

        try:
            self.cap.open(fd, camera_backend)
        except Exception:
            warnings.warn("Error while opening the camera")
            self.destroy()

    def destroy(self):
        if self.cap.isOpened():
            self.cap.release()
            self.cap = None

    def is_ended(self):
        return not self.cap.isOpened()

    def read(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return time.time_ns(), frame[..., ::-1]
            else:
                return time.time_ns(), None
