import logging
import cv2
import time


class CameraApp:
    def __init__(self, **kwargs):
        """
        Initializes the CameraApp instance.

        Args:
            **kwargs: Keyword arguments for configuring the camera.
                      Expected keys:
                      - fd (int or str): File descriptor or device index.
        """
        try:
            self.cap = cv2.VideoCapture()
            self.open(kwargs["fd"])
        except Exception:
            logging.error("Error while initializing the camera")
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
        except Exception:
            logging.error("Error while configuring the camera")
            self.destroy()

    def open(self, fd=0, camera_driver=cv2.CAP_DSHOW):
        try:
            self.cap.open(fd, camera_driver)
        except Exception:
            logging.error("Error while opening the camera")
            self.destroy()

    def destroy(self):
        if self.cap.isOpened():
            self.cap.release()
            self.cap = None

    def is_closed(self):
        return not self.cap.isOpened()

    def read(self):
        """
        Captures a frame from the camera.

        Returns:
            tuple: A tuple containing:
                - int: The current timestamp in nanoseconds.
                - numpy.ndarray or None: The captured frame in RGB format,
                  or None if the capture failed.
        """
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return time.time_ns(), cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                logging.warning("Failed to capture frame.")
        else:
            logging.warning("Camera is not opened.")

        return time.time_ns(), None
