import logging
import threading
import time
from collections import deque

import cv2
from PySide6.QtCore import QThread, Signal


CAMERA_FPS_WINDOW = 30
CAPTURE_IDLE_DELAY_S = 0.05
CAPTURE_STOP_TIMEOUT_S = 2.0

_stranded_workers = []


def strand_worker(worker):
    """
    Keep a reference to a capture worker that refused to stop.

    Dropping the last reference to a running QThread frees it while its run()
    is still executing, which kills the process without a traceback. Such a
    worker is deliberately leaked instead: it is still blocked inside a driver
    call, and the camera it reads from must stay open as well.

    Args:
        worker (CameraWorker): The worker that did not finish in time.
    """
    _stranded_workers.append(worker)


def stranded_workers():
    """
    list: Capture workers that were leaked because they did not stop in time.
    """
    return _stranded_workers


def stranded_worker_running():
    """
    bool: True while any leaked capture worker is still executing.
    """
    return any(worker.isRunning() for worker in _stranded_workers)


def camera_is_stranded(camera):
    """
    Report whether a leaked capture worker is still reading from a camera.

    Args:
        camera (CameraApp): The camera to check.

    Returns:
        bool: True while that camera must not be re-opened or released.
    """
    return any(worker.is_reading(camera) for worker in _stranded_workers)


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

    def is_reading(self, camera):
        """
        Report whether this worker is still reading from a given camera.

        Args:
            camera (CameraApp): The camera to check.

        Returns:
            bool: True while the loop runs against that camera.
        """
        return self._camera is camera and self.isRunning()

    def start(self, *args, **kwargs):
        """
        Start the capture loop; a worker that is already capturing is left alone.

        A loop that is still finishing a stop() which timed out cannot be
        restarted, because clearing the stop event would let it keep running.
        Waiting for it here would freeze the GUI for a second stop timeout, so
        the attempt fails immediately instead and the caller can try again once
        the driver has released the thread.

        Returns:
            bool: True when the capture loop is running afterwards.
        """
        if self.isRunning():
            if not self._stop_event.is_set():
                return True

            logging.error("Camera capture worker is still stopping; cannot restart it")
            return False

        self._stop_event.clear()
        self._intervals.clear()
        self._last_frame_at = None
        self._camera_fps = 0.0
        super().start(*args, **kwargs)
        return True

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
        """
        Capture frames until stop() is called.

        A failing camera must not kill the capture thread: an exception escaping
        run() would silently freeze the preview on the last frame, so every
        failure is logged and the loop keeps going after the usual back-off.
        """
        while not self._stop_event.is_set():
            try:
                captured = self.capture_once()
            except Exception:
                logging.exception("Error while capturing a camera frame")
                captured = False

            if not captured:
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

    def held_by_stranded_worker(self, action):
        """
        Refuse to touch the device while a leaked capture worker still reads it.

        A worker that never came back from read() keeps using this handle. Any
        other thread re-opening, re-configuring or releasing it would pull the
        capture out from under that call and take the whole process down, so the
        handle is intentionally leaked instead.

        Args:
            action (str): What the caller wanted to do, for the log message.

        Returns:
            bool: True when the request must be refused.
        """
        if not camera_is_stranded(self):
            return False

        logging.error(
            "Refusing to %s the camera: a leaked capture worker is still reading it", action
        )
        return True

    def settings(self):
        if self.cap is not None and not self.held_by_stranded_worker("open the settings of"):
            self.cap.set(cv2.CAP_PROP_SETTINGS, 1)

    def configure(self, **kwargs):
        try:
            if self.cap is None or self.held_by_stranded_worker("configure"):
                return
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, kwargs["width"])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, kwargs["height"])
        except Exception:
            logging.error("Error while configuring the camera")
            self.destroy()

    def open(self, fd=0, camera_driver=cv2.CAP_DSHOW):
        if self.held_by_stranded_worker("re-open"):
            return False

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
        if self.held_by_stranded_worker("release"):
            return

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
