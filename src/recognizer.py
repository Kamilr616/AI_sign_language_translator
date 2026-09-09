import time
import numpy as np
import custom_landmarks
import logging
import threading
from collections import deque
from dataclasses import dataclass
from camera import (
    CAPTURE_STOP_TIMEOUT_S,
    CameraApp,
    CameraWorker,
    LatestFrameBuffer,
    strand_worker,
)
from PySide6.QtCore import Signal, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QImage
from mediapipe import solutions, Image, ImageFormat
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.components import processors


INFERENCE_LATENCY_WINDOW = 30
INFERENCE_TIMEOUT_S = 1.0
INFERENCE_TIMEOUT_FACTOR = 10.0
INFERENCE_DEADLINE_MAX_S = 60.0
OUTSTANDING_INFERENCE_LIMIT = 8


@dataclass(frozen=True)
class PipelineMetrics:
    """
    Snapshot of the recognition pipeline throughput.

    Attributes:
        pipeline_fps (int): Recognition results delivered to the GUI per second.
        camera_fps (float): Frames per second delivered by the capture worker.
        inference_ms (float): Mean latency from recognize_async() to its callback.
        dropped_frames (int): Frames overwritten before the pipeline could consume
            them, counted cumulatively since the recognizer was created.
    """

    pipeline_fps: int
    camera_fps: float
    inference_ms: float
    dropped_frames: int


def create_scaled_qimage(frame: np.ndarray) -> QImage:
    """
    Converts a NumPy frame to QImage format and scales it to 640x480 only if needed.

    Args:
        frame (numpy.ndarray): The frame to convert (RGB).

    Returns:
        QImage: The detached and possibly scaled QImage.
    """
    h, w, ch = frame.shape
    image = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)

    if (w, h) != (640, 480):
        return image.scaled(QSize(640, 480), Qt.KeepAspectRatio, Qt.FastTransformation)

    return image.copy()


class GestureRecognizerApp(QObject):
    """
    A class to represent the gesture recognizer application.
    """
    result_ready_signal = Signal(object, list, list, object)
    recognize_next_signal = Signal()

    def __init__(self, model: str, num_hands: int, min_hand_detection_confidence: float,
                 min_hand_presence_confidence: float, min_tracking_confidence: float, score_confidence: float,
                 camera: CameraApp):
        """
        Initialize the gesture recognizer application with MediaPipe.

        Args:
            model (str): Path to the gesture recognizer model.
            num_hands (int): Number of hands to detect.
            min_hand_detection_confidence (float): Minimum confidence for hand detection.
            min_hand_presence_confidence (float): Minimum confidence for hand presence.
            min_tracking_confidence (float): Minimum confidence for tracking.
            score_confidence (float): Score threshold for gesture classification.
            camera (CameraApp): The camera object for capturing frames.
        """
        super().__init__()

        self.model = model
        self.num_hands = num_hands
        self.min_hand_detection_confidence = min_hand_detection_confidence
        self.min_hand_presence_confidence = min_hand_presence_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.score_confidence = score_confidence
        self.recognizer = None
        self._closing = False
        self._inference_pending = False
        self._retry_delay_ms = 50
        self.cap = camera
        self._frames = LatestFrameBuffer()
        self._worker = None

        self.last_timestamp_ms = 0
        self.fps_counter = 0
        self.fps = 0
        self.start_time = time.monotonic()
        self.inference_ms = 0.0
        self._inference_started_at = None
        self._pending_timestamp_ms = None
        self._outstanding = {}
        self._outstanding_lock = threading.Lock()
        self._latency_samples = deque(maxlen=INFERENCE_LATENCY_WINDOW)

        self.mp_hands = solutions.hands
        self.mp_drawing = solutions.drawing_utils
        self.drawing_styles = custom_landmarks
        self.recognize_next_signal.connect(
            self.recognize_frame,
            Qt.ConnectionType.QueuedConnection,
        )

    def create_recognizer(self):
        """
        Initialize the gesture recognizer with the specified model and options.
        """
        self._closing = False
        self._inference_pending = False
        self._inference_started_at = None
        self._pending_timestamp_ms = None
        self.forget_submissions()
        classifier_options = processors.ClassifierOptions(
            display_names_locale=None,
            max_results=1,
            score_threshold=self.score_confidence,
            category_allowlist=None,
            category_denylist=None
        )

        base_options = python.BaseOptions(model_asset_path=self.model)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=self.num_hands,
            min_hand_detection_confidence=self.min_hand_detection_confidence,
            min_hand_presence_confidence=self.min_hand_presence_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
            result_callback=self.handle_result,
            custom_gesture_classifier_options=classifier_options
        )
        self.recognizer = vision.GestureRecognizer.create_from_options(options)

        if self.cap.is_closed():
            return None

    @property
    def frames(self) -> LatestFrameBuffer:
        """LatestFrameBuffer: The buffer fed by the capture worker."""
        return self._frames

    @property
    def capture_busy(self) -> bool:
        """bool: True while the capture worker still holds the camera."""
        worker = self._worker
        return worker is not None and worker.isRunning()

    @property
    def camera_fps(self) -> float:
        """float: Frame rate delivered by the camera, 0.0 while capture is stopped."""
        worker = self._worker
        if worker is None or not worker.isRunning():
            return 0.0

        return worker.camera_fps

    def metrics(self) -> PipelineMetrics:
        """
        Collect the current throughput measurements.

        Returns:
            PipelineMetrics: Pipeline rate, camera rate, inference latency and drops.
        """
        return PipelineMetrics(
            pipeline_fps=self.fps,
            camera_fps=self.camera_fps,
            inference_ms=self.inference_ms,
            dropped_frames=self._frames.dropped_frames,
        )

    def start_capture(self) -> bool:
        """
        Start the camera capture worker and let it drive the recognition loop.

        Frames are captured on the worker thread, so the GUI thread is never
        blocked waiting for the camera sensor.

        Returns:
            bool: True when frames are being captured afterwards.
        """
        if self._closing:
            return False

        if self._worker is None:
            self._worker = CameraWorker(self.cap, self._frames)
            self._worker.frame_ready.connect(
                self.recognize_frame,
                Qt.ConnectionType.QueuedConnection,
            )

        return bool(self._worker.start())

    def stop_capture(self, timeout: float = CAPTURE_STOP_TIMEOUT_S) -> bool:
        """
        Stop the capture worker and discard the buffered frame.

        Args:
            timeout (float): Maximum wait for the capture thread, in seconds.

        Returns:
            bool: True when the capture thread finished within the timeout.
        """
        if self._worker is None:
            return True

        stopped = self._worker.stop(timeout)
        self._frames.clear()
        return stopped

    def handle_result(self, result: vision.GestureRecognizerResult, output_image: Image, timestamp_ms: int):
        """
        Callback to process and emit the gesture recognition result.

        Runs on a MediaPipe worker thread.

        A result for a packet the watchdog already gave up on is dropped: its
        bookkeeping now belongs to a newer submission, and the frame it carries
        is older than the one being recognized, so showing it would move the
        preview backwards. Its measured latency is still recorded, because that
        measurement is what widens the watchdog deadline.

        Args:
            result (GestureRecognizerResult): The recognition result containing detected gestures.
            output_image (Image): The processed output image.
            timestamp_ms (int): The timestamp of the result in milliseconds.
        """
        self.record_inference_latency(self.forget_submission(timestamp_ms))

        if timestamp_ms != self._pending_timestamp_ms:
            logging.warning("Ignoring a late recognition result for timestamp %s ms", timestamp_ms)
            return

        self._pending_timestamp_ms = None
        self._inference_started_at = None
        self._inference_pending = False
        try:
            frame, text, category_name = self.process_recognition_result(
                output_image.numpy_view().copy(), result
            )
            self.calculate_fps()
            self.result_ready_signal.emit(create_scaled_qimage(frame), text, category_name, self.metrics())
        except Exception as e:
            if not self._closing:
                logging.error(f"Error handling recognition result: {e}")
        finally:
            if self.recognizer and not self._closing:
                self.recognize_next_signal.emit()

    def remember_submission(self, timestamp_ms, started_at):
        """
        Note when a packet was submitted, so its latency can be measured later.

        The watchdog can hand the pipeline over to a newer submission before an
        older packet answers; keeping the start time of the last few packets lets
        such a late answer still be measured. The map is bounded, so a model that
        never answers cannot make it grow. Submissions are noted on the Qt thread
        and taken back on the MediaPipe thread, hence the lock. Its oldest-first
        eviction below, together with next_timestamp_ms()'s strictly increasing
        keys, is what lower_bound_latency() relies on to read a true lower bound
        off the head of this map.

        Args:
            timestamp_ms (int): The timestamp the packet was submitted with.
            started_at (float): The perf_counter() reading at submission.
        """
        with self._outstanding_lock:
            self._outstanding[timestamp_ms] = started_at

            while len(self._outstanding) > OUTSTANDING_INFERENCE_LIMIT:
                del self._outstanding[next(iter(self._outstanding))]

    def forget_submission(self, timestamp_ms):
        """
        Take back what was noted for a submission.

        Args:
            timestamp_ms (int): The timestamp the packet was submitted with.

        Returns:
            float or None: Its start time, or None when it is no longer known.
        """
        with self._outstanding_lock:
            return self._outstanding.pop(timestamp_ms, None)

    def forget_submissions(self):
        """Forget every noted submission."""
        with self._outstanding_lock:
            self._outstanding.clear()

    def lower_bound_latency(self):
        """
        Measure a packet whose start time is no longer remembered.

        remember_submission() evicts start times oldest first, and
        next_timestamp_ms() hands out strictly increasing keys, so the head of
        the map always holds the earliest still-remembered submission's start
        time. forget_submission() may pop arbitrary newer keys on callback, but
        that can only move the head forward in time, never backward — so the
        time since the oldest remembered submission can only shrink over time
        and is always a true lower bound on how long an unremembered packet has
        been outstanding. The measurement must come from the clock and never
        from the deadline, which is derived from these very samples — feeding
        it back in would make the mean grow without bound.

        Returns:
            float or None: The lower bound in seconds, or None when nothing is
            outstanding to measure against.
        """
        with self._outstanding_lock:
            oldest = next(iter(self._outstanding.values()), None)

        if oldest is None:
            oldest = self._inference_started_at

        if oldest is None:
            return None

        return time.perf_counter() - oldest

    def record_inference_latency(self, started_at):
        """
        Record how long one MediaPipe inference took.

        Measures the wall time between the recognize_async() submission and the
        callback entry, averaged over a rolling window so the readout does not
        flicker. Every answered packet contributes, including one the watchdog
        already abandoned: the rolling mean is what raises the watchdog deadline,
        so measuring only the accepted packets would pin the deadline at its
        floor and abandon every submission of a genuinely slower model forever.
        Called on the MediaPipe worker thread.

        A packet answered so late that its start time has already been forgotten
        still counts, measured against the oldest submission that is still
        remembered (see lower_bound_latency). Recording nothing there would leave
        the mean at zero for a model slower than the remembered window, and the
        deadline would stay pinned at its floor for good.

        Args:
            started_at (float or None): The perf_counter() reading taken when
                that packet was submitted, or None when it is no longer known.
        """
        if started_at is None:
            elapsed_s = self.lower_bound_latency()
            if elapsed_s is None:
                return

            latency_ms = elapsed_s * 1000.0
        else:
            latency_ms = (time.perf_counter() - started_at) * 1000.0

        self._latency_samples.append(latency_ms)
        self.inference_ms = sum(self._latency_samples) / len(self._latency_samples)

    def calculate_fps(self):
        """
        Calculate the pipeline frames per second (FPS): recognition results per second.
        """
        self.fps_counter += 1
        if self.fps_counter < 5:
            return

        current_time = time.monotonic()
        elapsed = current_time - self.start_time
        self.fps = round(5.0 / elapsed) if elapsed > 0 else 0
        self.start_time = current_time
        self.fps_counter = 0

    def _schedule_retry(self):
        """Retry capture without blocking the GUI or MediaPipe worker thread."""
        if self.recognizer and not self._closing:
            QTimer.singleShot(self._retry_delay_ms, self.recognize_frame)

    def inference_deadline_s(self) -> float:
        """
        How long to wait for a recognition callback before giving up on it.

        MediaPipe can drop a submitted packet in its flow limiter without ever
        calling back. Without a deadline the in-flight flag would stay set and
        every captured frame would be ignored from then on, freezing the app on
        its last result. The bound follows the rolling mean latency, which every
        answered packet feeds even when its result arrives too late to be used,
        so a model slower than the floor widens the deadline on its first answer
        instead of having all of its work abandoned.

        The result is capped: however the mean was arrived at, waiting minutes or
        hours for one callback is never useful, and a hard ceiling keeps a single
        extreme measurement from freezing the pipeline for the rest of the
        session. A model slower than the ceiling is beyond what this application
        can drive anyway, and it keeps resubmitting once per ceiling instead of
        stopping altogether.

        Returns:
            float: The deadline in seconds.
        """
        return min(
            INFERENCE_DEADLINE_MAX_S,
            max(INFERENCE_TIMEOUT_S, INFERENCE_TIMEOUT_FACTOR * self.inference_ms / 1000.0),
        )

    def inference_expired(self) -> bool:
        """
        bool: True when the pending inference has missed its deadline.
        """
        started_at = self._inference_started_at
        if started_at is None:
            return False

        return (time.perf_counter() - started_at) > self.inference_deadline_s()

    def next_timestamp_ms(self, timestamp_ns: int) -> int:
        """
        Convert a capture timestamp to the strictly increasing milliseconds MediaPipe requires.

        Two frames captured within the same millisecond would otherwise collide and
        make recognize_async() raise. The colliding frame is nudged one millisecond
        forward instead of being skipped: with a latest-wins buffer the frame at hand
        is the freshest one available, and dropping it would idle the pipeline until
        the next capture. MediaPipe only needs monotonicity, not wall-clock accuracy.

        Args:
            timestamp_ns (int): Monotonic capture timestamp in nanoseconds.

        Returns:
            int: A timestamp in milliseconds, strictly greater than the previous one.
        """
        timestamp_ms = timestamp_ns // 1_000_000

        if timestamp_ms <= self.last_timestamp_ms:
            timestamp_ms = self.last_timestamp_ms + 1

        self.last_timestamp_ms = timestamp_ms
        return timestamp_ms

    def recognize_frame(self):
        """
        Submits the newest captured frame for gesture recognition.

        Frames are produced by the capture worker; while an inference is in flight
        newly captured frames are dropped rather than queued, so the pipeline always
        works on the freshest frame. Doing nothing when no frame is buffered is the
        normal idle state: the next frame_ready signal resumes the loop.

        Returns:
            None: The function does not return a value but processes the frame asynchronously.
        """
        if self._closing or self.recognizer is None:
            return

        if self._inference_pending:
            if not self.inference_expired():
                return

            logging.warning(
                "No recognition result within %.0f ms; dropping the stalled inference",
                self.inference_deadline_s() * 1000.0,
            )
            self._inference_pending = False
            self._inference_started_at = None
            self._pending_timestamp_ms = None

        captured = self._frames.take()
        if captured is None:
            return

        timestamp, image = captured
        if image is None:
            return

        try:
            mp_image = Image(image_format=ImageFormat.SRGB, data=image.astype(np.uint8))
            timestamp_ms = self.next_timestamp_ms(timestamp)
            self._inference_started_at = time.perf_counter()
            self._pending_timestamp_ms = timestamp_ms
            self._inference_pending = True
            self.remember_submission(timestamp_ms, self._inference_started_at)
            self.recognizer.recognize_async(mp_image, timestamp_ms)
        except Exception as e:
            self._inference_pending = False
            self._inference_started_at = None
            self.forget_submission(self._pending_timestamp_ms)
            self._pending_timestamp_ms = None
            if not self._closing:
                logging.error(f"Exception in recognizer: {e}")
                self._schedule_retry()

    def process_recognition_result(self, frame, result):
        """
        Process the recognition result and draw landmarks on the frame.

        Args:
            frame (numpy.ndarray): The frame to process.
            result (vision.GestureRecognizerResult): The recognition result.

        Returns:
            tuple: Processed frame, text annotations, scores.
        """
        text = []
        scores = []

        if result.hand_landmarks:
            hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            hand_landmarks_proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in
                result.hand_landmarks[0]
            ])

            self.mp_drawing.draw_landmarks(frame, hand_landmarks_proto, self.mp_hands.HAND_CONNECTIONS,
                                           self.drawing_styles.get_hand_landmarks_style(),
                                           self.drawing_styles.get_hand_connections_style())

            if result.gestures:
                gesture = result.gestures[0]
                category_name = gesture[0].category_name
                gesture_score = gesture[0].score
                handedness = result.handedness[0]
                handedness_category_name = handedness[0].category_name
                handedness_score = handedness[0].score

                text = [category_name, handedness_category_name]
                scores = [gesture_score, handedness_score]

        return frame, text, scores

    def close(self, timeout: float = CAPTURE_STOP_TIMEOUT_S) -> bool:
        """
        Release resources: stop the capture worker first, then the recognizer.

        Args:
            timeout (float): Maximum wait for the capture thread, in seconds.

        Returns:
            bool: False when the capture thread did not stop in time. The worker
            is then leaked on purpose and the camera it reads from must be left
            open: freeing a running QThread, or releasing the VideoCapture it is
            blocked in, takes the whole process down without a traceback.
        """
        self._closing = True
        self._inference_pending = False
        self._pending_timestamp_ms = None
        self.forget_submissions()

        stopped = self.stop_capture(timeout)

        if self._worker is not None:
            self._worker.frame_ready.disconnect(self.recognize_frame)
            if not stopped:
                logging.error("Leaking the capture worker; the camera stays open")
                strand_worker(self._worker)
            self._worker = None

        if self.recognizer:
            self.recognizer.close()
            self.recognizer = None

        return stopped
