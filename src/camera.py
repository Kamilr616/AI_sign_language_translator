import logging
import threading
import time
from collections import deque

import cv2
from PySide6.QtCore import QThread, Signal


CAMERA_FPS_WINDOW = 30
CAPTURE_IDLE_DELAY_S = 0.05
CAPTURE_STOP_TIMEOUT_S = 2.0


class LatestFrameBuffer:
    """
    Single frame slot shared between the capture worker and its consumer.

    The worker always overwrites the slot ("latest wins"), so a slow consumer can
    never build up a backlog of stale frames; overwritten frames are counted as
    drops for diagnostics.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._item = None
        self._dropped = 0

    def put(self, timestamp, frame):
        """
        Store a frame, discarding an unconsumed one.

        Args:
            timestamp (int): Monotonic capture timestamp in nanoseconds.
            frame (numpy.ndarray): The captured frame.
        """
        with self._lock:
            if self._item is not None:
                self._dropped += 1
            self._item = (timestamp, frame)

    def take(self):
        """
        Remove and return the buffered frame.

        Returns:
            tuple or None: (timestamp_ns, frame) or None when the buffer is empty.
        """
        with self._lock:
            item = self._item
            self._item = None
            return item

    def clear(self):
        """Drop the buffered frame without counting it as a lost frame."""
        with self._lock:
            self._item = None

    @property
    def dropped_frames(self):
        """int: Frames overwritten before the consumer could read them."""
        with self._lock:
            return self._dropped


class CameraWorker(QThread):
    """
    Captures frames on a dedicated thread so that reading from the camera never
    blocks the GUI thread.

    Only the newest frame is kept (see LatestFrameBuffer); consumers are woken by
    the frame_ready signal instead of polling, so an idle consumer costs no CPU.
    """

    frame_ready = Signal()

    def __init__(self, camera, frame_buffer=None, fps_window=CAMERA_FPS_WINDOW,
                 idle_delay=CAPTURE_IDLE_DELAY_S, clock=time.monotonic, parent=None):
        """
        Args:
            camera (CameraApp): The camera to read frames from.
            frame_buffer (LatestFrameBuffer): Buffer shared with the consumer.
            fps_window (int): Number of frame intervals averaged into camera_fps.
            idle_delay (float): Pause after a failed capture, in seconds.
            clock (callable): Monotonic clock used for the frame rate measurement.
            parent (QObject): Optional Qt parent.
        """
        super().__init__(parent)
        self._camera = camera
        self._frames = frame_buffer if frame_buffer is not None else LatestFrameBuffer()
        self._intervals = deque(maxlen=max(1, fps_window))
        self._idle_delay = idle_delay
        self._clock = clock
        self._stop_event = threading.Event()
        self._last_frame_at = None
        self._camera_fps = 0.0

    @property
    def frames(self):
        """LatestFrameBuffer: The buffer holding the newest captured frame."""
        return self._frames

    @property
    def camera_fps(self):
        """float: Frame rate delivered by the camera, averaged over the window."""
        return self._camera_fps

    @property
    def dropped_frames(self):
        """int: Frames overwritten before the consumer could read them."""
        return self._frames.dropped_frames

    def start(self, *args, **kwargs):
        """Start the capture loop; a worker that is already running is left alone."""
        if self.isRunning():
            return

        self._stop_event.clear()
        self._intervals.clear()
        self._last_frame_at = None
        self._camera_fps = 0.0
        super().start(*args, **kwargs)

    def stop(self, timeout=CAPTURE_STOP_TIMEOUT_S):
        """
        Ask the capture loop to finish and wait for the thread to end.

        Args:
            timeout (float): Maximum wait in seconds.

        Returns:
            bool: True when the capture thread finished within the timeout.
        """
        self._stop_event.set()
        if not self.isRunning():
            return True

        finished = self.wait(int(timeout * 1000))
        if not finished:
            logging.error("Camera capture worker did not stop within %.1f s", timeout)

        return finished

    def run(self):
        """Capture frames until stop() is called."""
        while not self._stop_event.is_set():
            if not self.capture_once():
                self._stop_event.wait(self._idle_delay)

    def capture_once(self):
        """
        Read a single frame and publish it to the buffer.

        Returns:
            bool: True when a frame was captured and published.
        """
        if self._camera is None or self._camera.is_closed():
            return False

        timestamp, frame = self._camera.read()
        if frame is None:
            return False

        self._record_frame_interval()
        self._frames.put(timestamp, frame)
        self.frame_ready.emit()
        return True

    def _record_frame_interval(self):
        """Update the rolling camera frame rate from the interval between frames."""
        now = self._clock()
        if self._last_frame_at is not None:
            self._intervals.append(now - self._last_frame_at)
        self._last_frame_at = now

        elapsed = sum(self._intervals)
        self._camera_fps = len(self._intervals) / elapsed if elapsed > 0 else 0.0


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
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_SETTINGS, 1)

    def configure(self, **kwargs):
        try:
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
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        self.cap = None

    def is_closed(self):
        return self.cap is None or not self.cap.isOpened()

    def read(self):
        """
        Captures a frame from the camera.

        The timestamp comes from a monotonic clock, so it never jumps backwards
        when the system clock is adjusted; MediaPipe requires strictly increasing
        timestamps.

        Returns:
            tuple: A tuple containing:
                - int: The current monotonic timestamp in nanoseconds.
                - numpy.ndarray or None: The captured frame in RGB format,
                  or None if the capture failed.
        """
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return time.monotonic_ns(), cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                logging.warning("Failed to capture frame.")
        else:
            logging.warning("Camera is not opened.")

        return time.monotonic_ns(), None
