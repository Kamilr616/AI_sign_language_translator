from recognizer import GestureRecognizerApp
from gui import *
from speaker import TextToSpeech
from camera import *

MODEL_PATH = '../models/gesture_recognizer_asl_13.task'
#CAMERA_ID = 0
# CAMERA_WIDTH = 640
# CAMERA_HEIGHT = 480
CAMERA_FPS = 30
#QUEUE_SIZE = 10



class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        """
        Initialize the main application window and connect UI elements to their methods.
        """
        super(MainApp, self).__init__()
        self.setupUi(self)

        self.camera_app = None
        self.recognizer_app = None
        self.tts_app = None
        self.checkbox_1_flag = False

        # Connect UI elements to their methods
        self.checkBox_speak.stateChanged.connect(self.checkbox_speak_change)
        self.pushButton_plus.clicked.connect(self.pushbutton_plus_click)
        self.pushButton_resetRecognizer.clicked.connect(self.reset_recognizer)
        self.pushButton_resetTTS.clicked.connect(self.reset_tts)
        #self.pushButton_speak.clicked.connect(self.pushbutton_speak_click)
        self.pushButton_resetCap.clicked.connect(self.pushbutton_reset_cap_click)

    def init_camera(self):
        try:
            self.camera_app = AsyncCamera(fd=self.spinBox_cameraID.value(), width=self.spinBox_camera_width.value(),
                                          height=self.spinBox_camera_height.value())
        except Exception as e:
            print(f"Error while init camera: {e.args}")

    def reset_camera(self):
        """
        Reset the camera application with new settings.
        """
        try:
            self.camera_app.configure(width=self.spinBox_camera_width.value(), height=self.spinBox_camera_height.value())
            self.camera_app.open(fd=self.spinBox_cameraID.value())
        except Exception as e:
            print(f"Error while resetting camera: {e.args}")

    def reset_tts(self):
        """
        Reset the text-to-speech engine with new settings.
        """
        if self.tts_app is not None:
            self.tts_app.stop()

        self.tts_app = TextToSpeech(
            rate=self.spinBox_ttsRate.value(),
            volume=(self.spinBox_volume.value() / 100.0))

    def reset_recognizer(self):
        """
        Reset the gesture recognizer with new settings.
        """
        if self.recognizer_app is not None:
            if self.recognizer_app.result_ready_signal:
                self.recognizer_app.result_ready_signal.disconnect()
            self.recognizer_app.close()
            self.recognizer_app = None

        if self.camera_app is not None:
            self.recognizer_app = GestureRecognizerApp(
                model=MODEL_PATH,
                num_hands=1,
                min_hand_detection_confidence=(self.spinBox_detection.value() / 100.0),
                min_hand_presence_confidence=(self.spinBox_presence.value() / 100.0),
                min_tracking_confidence=(self.spinBox_tracking.value() / 100.0),
                score_confidence=(self.spinBox_treshold.value() / 100.0),
                camera=self.camera_app
            )
            self.recognizer_app.result_ready_signal.connect(self.update_frame)
            self.recognizer_app.start()
            self.recognizer_app.recognize_frame()

    def start(self):
        """
        Start the gesture recognizer application if not already started.
        """
        if not self.camera_app:
            self.init_camera()

        if not self.tts_app:
            self.reset_tts()

        if not self.recognizer_app:
            self.reset_recognizer()

    def update_frame(self, frame, text, scores, latest_fps):
        """
        Update the UI with the processed frame and recognized gesture text.

        Args:
            frame (QPixmap): The processed frame.
            text (list): Recognized gesture text.
            scores (list): Scores of the recognized gestures.
            latest_fps (float): The latest frames per second (FPS) value.
        """
        if frame:
            self.label_displayFrame.setPixmap(frame)

        if latest_fps:
            self.label_displayFPS.setText(f'{latest_fps:.1f} FPS')

        if text and scores:
            self.label_recognitionInfo.setText(f'{text[1]} {scores[1]:.0%}')
            if text[0] != "":
                self.label_displaySign.setText(text[0])
            else:
                self.label_displaySign.setText('?')
            self.progressBar_1.setValue(scores[0] * 100)

            if self.checkbox_1_flag:
                self.translate_to_speech(text[0])
        else:
            self.label_recognitionInfo.setText('Not detected')
            self.label_displaySign.setText('-')
            self.progressBar_1.setValue(0)


    def translate_to_speech(self, data=""):
        """
        Translate the recognized gesture text to speech.

        Args:
            data (str): The recognized gesture text.
         """
        if self.tts_app is not None:
            self.tts_app.speak(data)

    def checkbox_speak_change(self):
        """
        Toggle the auto mode for text-to-speech.
        """
        self.checkbox_1_flag = not self.checkbox_1_flag

    # def pushbutton_speak_click(self):
    #     """
    #     Manually trigger text-to-speech translation.
    #     """
    #     self.translate_to_speech(self.label_displaySign.text())

    def pushbutton_plus_click(self):
        """
        Placeholder for future functionality.
        """
        self.recognizer_app.recognize_frame()

    def pushbutton_reset_cap_click(self):
        """
        Reset Camera.
        """
        self.recognizer_app.close()
        self.reset_camera()
        self.recognizer_app.start()
        self.recognizer_app.recognize_frame()

    def closeEvent(self, event):
        """
        Release resources when closing the application.

        Args:
            event (QCloseEvent): The close event.
        """
        if self.recognizer_app is not None:
            if self.recognizer_app.result_ready_signal:
                self.recognizer_app.result_ready_signal.disconnect()
            self.recognizer_app.close()
            self.recognizer_app = None

        if self.camera_app is not None:
            self.camera_app.destroy()
            self.camera_app = None

        if self.tts_app is not None:
            self.tts_app.stop()
            self.tts_app = None

        super().closeEvent(event)