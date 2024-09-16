import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2


class GestureRecognizerApp:
    """
    A class to represent the gesture recognizer application.
    """

    def __init__(self, model: str, num_hands: int, min_hand_detection_confidence: float,
                 min_hand_presence_confidence: float, min_tracking_confidence: float,
                 camera_id: int, width: int, height: int):
        """
        Initialize the gesture recognizer application with MediaPipe.
        """
        self.recognizer = None
        self.cap = None
        self.model = model
        self.num_hands = num_hands
        self.min_hand_detection_confidence = min_hand_detection_confidence
        self.min_hand_presence_confidence = min_hand_presence_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.camera_id = camera_id
        self.width = width
        self.height = height

        # Initialize other state variables
        self.image = None
        self.output_text = None
        self.counter = 0
        self.fps = 0
        self.start_time = time.time()
        self.result_ready = False
        self.recognition_result = None
        self.recognition_frame = None
        self.is_recognition_active = True

        # MediaPipe drawing and gesture recognizer setup
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def initialize_camera(self):
        """ Initialize the camera and gesture recognizer. """
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open camera {self.camera_id}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        base_options = python.BaseOptions(model_asset_path=self.model)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=self.num_hands,
            min_hand_detection_confidence=self.min_hand_detection_confidence,
            min_hand_presence_confidence=self.min_hand_presence_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
            result_callback=self.save_result
        )
        self.recognizer = vision.GestureRecognizer.create_from_options(options)


    def save_result(self, result: vision.GestureRecognizerResult, output_image: mp.Image, timestamp_ms: int):
        """
        Callback to save the recognition result.
        """
        if self.counter % 10 == 0:
            self.fps = 10 / (time.time() - self.start_time)
            self.start_time = time.time()
        self.counter += 1

        self.recognition_result = result
        self.result_ready = True
        self.is_recognition_active = False

    def recognize_frame(self):

        success, self.image = self.cap.read()
        if not success:
            self.image = None
            return

        if self.is_recognition_active:
            # Convert image to mp.Image
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB))
            self.recognizer.recognize_async(mp_image, time.time_ns() // 1_000_000)

    def get_frame(self, nolag):
        cv2.putText(self.image, f'{self.fps:.1f} FPS', (24, 45), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 0), 1)

        if self.result_ready:
            self.process_recognition_result(self.image)
            self.result_ready = False
            return self.recognition_frame, self.output_text

        if nolag:
            return self.image, None

        return self.recognition_frame, None

    def process_recognition_result(self, frame):
        """
        Process the recognition result and draw landmarks on the frame.
        """

        for hand_index, hand_landmarks in enumerate(self.recognition_result.hand_landmarks):
            hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            hand_landmarks_proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in hand_landmarks
            ])

            self.mp_drawing.draw_landmarks(frame, hand_landmarks_proto, self.mp_hands.HAND_CONNECTIONS,
                                           self.mp_drawing_styles.get_default_hand_landmarks_style(),
                                           self.mp_drawing_styles.get_default_hand_connections_style())

        if self.recognition_result.gestures:
            gesture = self.recognition_result.gestures[hand_index]
            category_name = gesture[0].category_name
            score = round(gesture[0].score, 3)
            handedness = self.recognition_result.handedness[hand_index]
            handedness_category_name = handedness[0].category_name
            handedness_score = round(handedness[0].score, 3)

            self.output_text = f'Sign: {category_name} ({format(score, ".1%")}) Hand: {handedness_category_name} ({format(handedness_score, ".1%")})'

        self.recognition_frame = frame
        self.is_recognition_active = True

    def close(self):
        """Release resources."""
        if self.cap.isOpened():
            self.cap.release()
        self.recognizer.close()
