import time
import mediapipe as mp
import custom_landmarks
from camera_capture import AsyncCamera
from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QPixmap, QImage
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.components import processors


def convert_frame_qpixmap(frame):
    """
    Convert a frame to QPixmap format.

    Args:
        frame (numpy.ndarray): The frame to convert.

    Returns:
        QPixmap: The converted QPixmap.
    """
    h, w, ch = frame.shape
    image = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(image)


class GestureRecognizerApp(QObject):
    """
    A class to represent the gesture recognizer application.
    """
    result_ready_signal = Signal(object, list, list, float)

    def __init__(self, model: str, num_hands: int, min_hand_detection_confidence: float,
                 min_hand_presence_confidence: float, min_tracking_confidence: float, score_treshold: float,
                 camera_id: int, width: int, height: int):
        """
        Initialize the gesture recognizer application with MediaPipe.

        Args:
            model (str): Path to the gesture recognizer model.
            num_hands (int): Number of hands to detect.
            min_hand_detection_confidence (float): Minimum confidence for hand detection.
            min_hand_presence_confidence (float): Minimum confidence for hand presence.
            min_tracking_confidence (float): Minimum confidence for tracking.
            score_treshold (float): Score threshold for gesture classification.
            camera_id (int): Camera ID to use.
            width (int): Width of the camera frame.
            height (int): Height of the camera frame.
        """
        super().__init__()

        self.model = model
        self.num_hands = num_hands
        self.min_hand_detection_confidence = min_hand_detection_confidence
        self.min_hand_presence_confidence = min_hand_presence_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.score_treshold = score_treshold

        self.recognizer = None
        self.cap = None

        # Initialize state variables
        self.counter = 0
        self.fps = 0.0
        self.start_time = time.time()

        # MediaPipe drawing and gesture recognizer setup
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        
        # Custom landmarks
        self.drawing_styles = custom_landmarks

    def start(self):
        """
        Initialize the camera and gesture recognizer.
        """
        classifier_options = processors.ClassifierOptions(
            display_names_locale=None,
            max_results=1,
            score_threshold=self.score_treshold,
            category_allowlist=None,
            category_denylist=['space', 'del']
        )

        base_options = python.BaseOptions(model_asset_path=self.model)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=self.num_hands,
            min_hand_detection_confidence=self.min_hand_detection_confidence,
            min_hand_presence_confidence=self.min_hand_presence_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
            result_callback=self.save_result,
            custom_gesture_classifier_options=classifier_options
        )
        self.recognizer = vision.GestureRecognizer.create_from_options(options)

        self.cap = AsyncCamera(self.camera_id, fps=30, width=self.width, height=self.height, format='mjpeg')

        if self.cap.is_ended():
            return  # TODO: Exception ?(raise IOError(f"Cannot open camera {self.camera_id}"))

    def save_result(self, result: vision.GestureRecognizerResult, output_image: mp.Image, timestamp_ms: int):
        """
        Callback to save the recognition result.

        Args:
            result (vision.GestureRecognizerResult): The recognition result.
            output_image (mp.Image): The output image.
            timestamp_ms (int): The timestamp of the result.
        """
        frame, text, category_name, latest_fps = self.process_single_recognition_result(
            output_image.numpy_view().copy(), result)
        self.result_ready_signal.emit(convert_frame_qpixmap(frame), text, category_name, latest_fps)
        self.recognize_frame()
        self.calculate_fps()

    def calculate_fps(self):
        """
        Calculate the frames per second (FPS).
        """
        if self.counter % 10 == 0:
            self.fps = 10.0 / (time.time() - self.start_time)
            self.start_time = time.time()
        self.counter += 1

    def recognize_frame(self):
        """
        Capture a frame from the camera and run gesture recognition.
        """
        if not self.cap:
            return None

        success, image = self.cap.read()
        if not success:
            return None

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        self.recognizer.recognize_async(mp_image, time.time_ns() // 1_000_000)

    def get_frame(self):
        """
        Capture a frame from the camera.

        Returns:
            QPixmap: The captured frame in QPixmap format.
        """
        if not self.cap:
            return None

        success, image = self.cap.read()
        if not success:
            return None

        return convert_frame_qpixmap(image)

    def process_single_recognition_result(self, frame, result):
        """
        Process the recognition result and draw landmarks on the frame.

        Args:
            frame (numpy.ndarray): The frame to process.
            result (vision.GestureRecognizerResult): The recognition result.

        Returns:
            tuple: Processed frame, text annotations, scores, and latest FPS.
        """
        text = []
        scores = []
        latest_fps = self.fps

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

        return frame, text, scores, latest_fps

    def close(self):
        """
        Release resources.
        """
        if not self.cap.is_ended():
            self.cap.destroy()
            self.cap = None

        if self.recognizer:
            self.recognizer.close()
            self.recognizer = None
