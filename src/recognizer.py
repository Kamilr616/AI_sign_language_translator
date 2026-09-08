import time
import numpy as np
import custom_landmarks
import logging
from camera import CameraApp
from PySide6.QtCore import Signal, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QImage
from mediapipe import solutions, Image, ImageFormat
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.components import processors


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
    result_ready_signal = Signal(object, list, list, int)
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

        self.last_timestamp = 0
        self.fps_counter = 0
        self.fps = 0
        self.start_time = time.time()

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

    def handle_result(self, result: vision.GestureRecognizerResult, output_image: Image, timestamp_ms: int):
        """
        Callback to process and emit the gesture recognition result.

        Args:
            result (GestureRecognizerResult): The recognition result containing detected gestures.
            output_image (Image): The processed output image.
            timestamp_ms (int): The timestamp of the result in milliseconds.
        """
        self._inference_pending = False
        try:
            frame, text, category_name = self.process_recognition_result(
                output_image.numpy_view().copy(), result
            )
            self.calculate_fps()
            self.result_ready_signal.emit(create_scaled_qimage(frame), text, category_name, self.fps)
        except Exception as e:
            if not self._closing:
                logging.error(f"Error handling recognition result: {e}")
        finally:
            if self.recognizer and not self._closing:
                self.recognize_next_signal.emit()

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

    def _schedule_retry(self):
        """Retry capture without blocking the GUI or MediaPipe worker thread."""
        if self.recognizer and not self._closing:
            QTimer.singleShot(self._retry_delay_ms, self.recognize_frame)

    def recognize_frame(self):
        """
        Captures a frame from the camera and processes it for gesture recognition.

        Returns:
            None: The function does not return a value but processes the frame asynchronously.
        """
        if self._closing or self.recognizer is None:
            return

        if self._inference_pending:
            return

        if self.cap.is_closed():
            logging.warning("Camera is not opened or recognizer is not initialized.")
            return

        timestamp, image = self.cap.read()

        while image is not None and timestamp <= self.last_timestamp:
            logging.warning(f"Skipping outdated frame: {timestamp}")
            timestamp, image = self.cap.read()

        if image is not None:
            try:
                mp_image = Image(image_format=ImageFormat.SRGB, data=image.astype(np.uint8))
                self.last_timestamp = timestamp
                self._inference_pending = True
                self.recognizer.recognize_async(mp_image, timestamp // 1_000_000)
            except Exception as e:
                self._inference_pending = False
                if not self._closing:
                    logging.error(f"Exception in recognizer: {e}")
                    self._schedule_retry()
        else:
            logging.warning("No valid image to recognize.")
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

    def close(self):
        """
        Release resources.
        """
        self._closing = True
        self._inference_pending = False
        if self.recognizer:
            self.recognizer.close()
            self.recognizer = None
