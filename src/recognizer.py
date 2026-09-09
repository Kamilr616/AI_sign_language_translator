import time
import numpy as np
import custom_landmarks
import logging
from collections import deque
from dataclasses import dataclass
from camera import CAPTURE_STOP_TIMEOUT_S, CameraApp, CameraWorker, LatestFrameBuffer
from PySide6.QtCore import Signal, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QImage
from mediapipe import solutions, Image, ImageFormat
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.components import processors


INFERENCE_LATENCY_WINDOW = 30


@dataclass(frozen=True)
class PipelineMetrics:
    """
    Snapshot of the recognition pipeline throughput.

    Attributes:
        pipeline_fps (int): Recognition results delivered to the GUI per second.
        camera_fps (float): Frames per second delivered by the capture worker.
        inference_ms (float): Mean latency from recognize_async() to its callback.
        dropped_frames (int): Frames captured while an inference was in flight.
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
    def camera_fps(self) -> float:
        """float: Frame rate delivered by the camera, 0.0 while capture is stopped."""
        return self._worker.camera_fps if self._worker is not None else 0.0

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

    def start_capture(self):
        """
        Start the camera capture worker and let it drive the recognition loop.

        Frames are captured on the worker thread, so the GUI thread is never
        blocked waiting for the camera sensor.
        """
        if self._closing:
            return

        if self._worker is None:
            self._worker = CameraWorker(self.cap, self._frames)
            self._worker.frame_ready.connect(
                self.recognize_frame,
                Qt.ConnectionType.QueuedConnection,
            )

        self._worker.start()

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

        Args:
            result (GestureRecognizerResult): The recognition result containing detected gestures.
            output_image (Image): The processed output image.
            timestamp_ms (int): The timestamp of the result in milliseconds.
        """
        self._inference_pending = False
        self.record_inference_latency()
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

    def record_inference_latency(self):
        """
        Record how long the last MediaPipe inference took.

        Measures the wall time between the recognize_async() submission and the
        callback entry, averaged over a rolling window so the readout does not
        flicker. Called on the MediaPipe worker thread.
        """
        started_at = self._inference_started_at
        self._inference_started_at = None

        if started_at is None:
            return

        self._latency_samples.append((time.perf_counter() - started_at) * 1000.0)
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
            return

        captured = self._frames.take()
        if captured is None:
            return

        timestamp, image = captured
        if image is None:
            return

        try:
            mp_image = Image(image_format=ImageFormat.SRGB, data=image.astype(np.uint8))
            self._inference_pending = True
            self._inference_started_at = time.perf_counter()
            self.recognizer.recognize_async(mp_image, self.next_timestamp_ms(timestamp))
        except Exception as e:
            self._inference_pending = False
            self._inference_started_at = None
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

    def close(self):
        """
        Release resources: stop the capture worker first, then the recognizer.
        """
        self._closing = True
        self._inference_pending = False

        self.stop_capture()
        if self._worker is not None:
            self._worker.frame_ready.disconnect(self.recognize_frame)
            self._worker = None

        if self.recognizer:
            self.recognizer.close()
            self.recognizer = None
