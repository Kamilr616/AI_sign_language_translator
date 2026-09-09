import logging
import threading
import time

import custom_landmarks
import numpy as np
from camera import CameraApp
from mediapipe import Image, ImageFormat, solutions
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.components import processors
from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QImage


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

    Frames are read on a dedicated capture thread (``CaptureWorker``) so that
    neither the Qt main thread nor the MediaPipe callback thread ever blocks on
    ``cv2.VideoCapture.read()``. At most one ``recognize_async`` call is in
    flight; while a result is pending the worker keeps reading and drops frames,
    so the next submission is always the newest frame the camera has produced.
    """
    result_ready_signal = Signal(object, list, list, int)

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
        self._pending_since = 0.0
        self._pending_timeout_s = 2.0
        self._slot_free = threading.Event()
        self._slot_free.set()
        # How long a fresh frame waits for the in-flight result before it is
        # dropped in favour of the next one (about half a frame at 30 FPS).
        self._drop_after_s = 0.015
        self._retry_delay_s = 0.05
        self._capture_thread = None
        self._stop_capture = threading.Event()
        self._capture_failing = False
        self.cap = camera

        # Milliseconds of the last frame handed to MediaPipe; the next one is
        # always at least one millisecond later.
        self.last_timestamp = 0
        self.fps_counter = 0
        self.fps = 0
        self.start_time = time.time()

        self.mp_hands = solutions.hands
        self.mp_drawing = solutions.drawing_utils
        self.drawing_styles = custom_landmarks

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

    def handle_result(self, result: vision.GestureRecognizerResult, output_image: Image, timestamp_ms: int):
        """
        Callback to process and emit the gesture recognition result.

        Runs on the MediaPipe worker thread. Releasing the in-flight slot first
        lets the capture worker submit the next frame while this one is drawn.

        Args:
            result (GestureRecognizerResult): The recognition result containing detected gestures.
            output_image (Image): The processed output image.
            timestamp_ms (int): The timestamp of the result in milliseconds.
        """
        self._release_slot()
        try:
            frame, text, category_name = self.process_recognition_result(
                output_image.numpy_view().copy(), result
            )
            self.calculate_fps()
            self.result_ready_signal.emit(create_scaled_qimage(frame), text, category_name, self.fps)
        except Exception as e:
            if not self._closing:
                logging.error(f"Error handling recognition result: {e}")

    def calculate_fps(self):
        """
        Calculate the frames per second (FPS).
        """
        self.fps_counter += 1
        if self.fps_counter < 5:
            return

        current_time = time.time()
        elapsed = current_time - self.start_time
        self.fps = round(5.0 / elapsed) if elapsed > 0 else 0
        self.start_time = current_time
        self.fps_counter = 0

    def recognize_frame(self):
        """
        Start the capture loop on its worker thread.

        Does nothing while the recognizer is closed, not created yet, or the
        worker is already running, so it is safe to call after every reset.
        """
        if self._closing or self.recognizer is None:
            return

        thread = self._capture_thread
        if thread is not None and thread.is_alive():
            return

        self._stop_capture.clear()
        self._capture_thread = threading.Thread(
            target=self._capture_loop, name="CaptureWorker", daemon=True)
        self._capture_thread.start()

    def stop_capture(self, timeout=2.0):
        """
        Stop the capture loop and wait for the worker to exit.

        Returns:
            bool: True when the worker is gone, False when it is still busy in a
                  blocking camera read after the timeout.
        """
        self._stop_capture.set()
        thread = self._capture_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
            if thread.is_alive():
                logging.warning("Capture worker did not stop within %.1fs", timeout)
                return False
        self._capture_thread = None
        return True

    def _capture_loop(self):
        """Read frames until stopped; submit whenever no result is pending."""
        while not self._stop_capture.is_set():
            if self._closing or self.recognizer is None:
                return

            if self.cap.is_closed():
                self._note_capture_failure("Camera is not opened.")
                self._stop_capture.wait(self._retry_delay_s)
                continue

            timestamp, image = self.cap.read()
            if image is None:
                self._note_capture_failure("No valid image to recognize.")
                self._stop_capture.wait(self._retry_delay_s)
                continue
            self._capture_failing = False

            if self._inference_pending and not self._slot_free.wait(self._drop_after_s):
                if time.monotonic() - self._pending_since < self._pending_timeout_s:
                    # The previous result is still pending: drop this frame and
                    # read a fresher one instead of queueing stale frames.
                    continue
                logging.warning(
                    "No result from the recognizer within %.1fs, resuming submission",
                    self._pending_timeout_s)
                self._release_slot()

            if not self.submit_frame(image, timestamp):
                self._stop_capture.wait(self._retry_delay_s)

    def _note_capture_failure(self, message):
        """Log a capture failure once per failure episode instead of every retry."""
        if not self._capture_failing:
            logging.warning(message)
            self._capture_failing = True

    def _release_slot(self):
        """Mark the single in-flight inference as finished."""
        self._inference_pending = False
        self._slot_free.set()

    def submit_frame(self, image, timestamp_ns):
        """
        Hand one RGB frame to MediaPipe.

        MediaPipe requires strictly increasing millisecond timestamps, so the
        nanosecond capture time is converted and bumped to at least one
        millisecond after the previous submission.

        Returns:
            bool: True when the frame was accepted, False on a submission error.
        """
        timestamp_ms = max(timestamp_ns // 1_000_000, self.last_timestamp + 1)
        try:
            mp_image = Image(
                image_format=ImageFormat.SRGB,
                data=np.ascontiguousarray(image, dtype=np.uint8),
            )
            self._slot_free.clear()
            self._inference_pending = True
            self._pending_since = time.monotonic()
            self.recognizer.recognize_async(mp_image, timestamp_ms)
            self.last_timestamp = timestamp_ms
            return True
        except Exception as e:
            self._release_slot()
            if not self._closing:
                logging.error(f"Exception in recognizer: {e}")
            return False

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
                handedness = result.handedness[0]
                handedness_category_name = handedness[0].category_name
                handedness_score = handedness[0].score

                # When no sign passes the score threshold (this includes the trained
                # ``none`` class), MediaPipe does not return an empty list but a
                # background category: index -1, an empty name, and a score that is
                # not the confidence of any sign. Report it as "hand seen, no sign".
                if gesture and gesture[0].category_name:
                    text = [gesture[0].category_name, handedness_category_name]
                    scores = [gesture[0].score, handedness_score]
                else:
                    text = ['', handedness_category_name]
                    scores = [0.0, handedness_score]

        return frame, text, scores

    def close(self, timeout=2.0):
        """
        Stop the capture worker and release MediaPipe resources.

        MediaPipe is closed either way: once ``_closing`` is set the loop never
        submits again, and a submission racing with the close fails quietly.

        Returns:
            bool: True when the worker is gone, False when it was still inside
                  a blocking camera read after the timeout. In that case the
                  worker still holds the camera lock, so the caller must not
                  reopen, reconfigure or release the device until it exits.
        """
        self._closing = True
        stopped = self.stop_capture(timeout)
        self._release_slot()
        if self.recognizer:
            self.recognizer.close()
            self.recognizer = None
        return stopped
