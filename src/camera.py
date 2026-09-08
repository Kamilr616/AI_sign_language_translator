import logging
import threading
import time

import cv2


class CameraApp:
    def __init__(self, **kwargs):
        """
        Initializes the CameraApp instance.

        Args:
            **kwargs: Keyword arguments for configuring the camera.
                      Expected keys:
                      - fd (int or str): File descriptor or device index.
        """
        self.cap = None
        # The capture worker reads on its own thread while the GUI thread may
        # reopen or reconfigure the device; every VideoCapture call is serialised.
        self._lock = threading.Lock()
        try:
            self.cap = cv2.VideoCapture()
            self.open(
                kwargs["fd"],
                kwargs.get("camera_driver", cv2.CAP_DSHOW),
            )
            self.configure(**kwargs)
        except Exception:
            logging.exception("Error while initializing the camera")
            self.destroy()

    def settings(self):
        with self._lock:
            if self.cap is not None:
                self.cap.set(cv2.CAP_PROP_SETTINGS, 1)

    def configure(self, **kwargs):
        try:
            with self._lock:
                if self.cap is None:
                    return
                self.cap.set(cv2.CAP_PROP_FPS, 30)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, kwargs["width"])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, kwargs["height"])
        except Exception:
            logging.error("Error while configuring the camera")
            self.destroy()

    def open(self, fd=0, camera_driver=cv2.CAP_DSHOW):
        try:
            with self._lock:
                if self.cap is None:
                    self.cap = cv2.VideoCapture()
                opened = self.cap.open(fd, camera_driver)
            if not opened:
                logging.error("Could not open camera %s with backend %s", fd, camera_driver)
            return opened
        except Exception:
            logging.exception("Error while opening the camera")
            self.destroy()
            return False

    def destroy(self):
        with self._lock:
            if self.cap is not None and self.cap.isOpened():
                self.cap.release()
            self.cap = None

    def is_closed(self):
        cap = self.cap
        return cap is None or not cap.isOpened()

    def read(self):
        """
        Captures a frame from the camera.

        Returns:
            tuple: A tuple containing:
                - int: A monotonic timestamp in nanoseconds (immune to wall-clock
                  adjustments, so it never runs backwards).
                - numpy.ndarray or None: The captured frame in RGB format,
                  or None if the capture failed.
        """
        with self._lock:
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    return time.monotonic_ns(), cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                logging.warning("Failed to capture frame.")
            else:
                logging.warning("Camera is not opened.")

        return time.monotonic_ns(), None
