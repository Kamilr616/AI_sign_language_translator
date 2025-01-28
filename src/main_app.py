from recognizer import GestureRecognizerApp
from gui import *
from speaker import TextToSpeech
from camera import *

MODEL_PATH = '../models/gesture_recognizer_asl_13.task'
CAMERA_FPS = 30


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
        self.last_results = []

        # Connect UI elements to their methods
        #self.pushButton_plus.clicked.connect(self.pushbutton_plus_click)
        self.pushButton_resetRecognizer.clicked.connect(self.reset_recognizer)
        self.pushButton_resetTTS.clicked.connect(self.reset_tts)
        self.pushButton_resetCap.clicked.connect(self.pushbutton_reset_cap_click)
        self.spinBox_avg_count.valueChanged.connect(self.last_results.clear)
        self.pushButton_camera_settings.clicked.connect(self.pushbutton_camera_settings_click)
        self.spinBox_cameraID.setMaximum(count_available_cameras() -1)


    def pushbutton_camera_settings_click(self):
        if self.camera_app:
            self.camera_app.settings()

    def init_camera(self):
        try:
            self.camera_app = CameraApp(fd=self.spinBox_cameraID.value(), width=self.spinBox_camera_width.value(),
                                        height=self.spinBox_camera_height.value())
        except Exception as e:
            print(f"Error while init camera: {e.args}")

    def reset_camera(self):
        """
        Reset the camera application with new settings.
        """
        try:
            self.camera_app.open(fd=self.spinBox_cameraID.value(), direct_show=self.checkBox_direct_show.isChecked())
            self.camera_app.configure(width=self.spinBox_camera_width.value(), height=self.spinBox_camera_height.value())

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

    def calculate_common_sign_and_average(self):
        """
        Calculate the most common sign and the average score for that sign.

        Returns:
            tuple: A tuple containing the most common sign (str) and its average score (float).
        """
        if not self.last_results:
            return "", 0.0

        if len(self.last_results) > self.spinBox_avg_count.value():
            self.last_results.pop(0)

        # most_common_sign, _ = max(set(self.last_results), key=self.last_results.count)
        # scores_for_common_sign = [score for sign, score in self.last_results if sign == most_common_sign]
        # average_score = sum(scores_for_common_sign) / len(scores_for_common_sign)
        sign_count = {}
        sign_scores = {}

        for sign, score in self.last_results:
            if sign in sign_count:
                sign_count[sign] += 1
                sign_scores[sign] += score
            else:
                sign_count[sign] = 1
                sign_scores[sign] = score

        most_common_sign = max(sign_count, key=sign_count.get)
        average_score = sign_scores[most_common_sign] / sign_count[most_common_sign]

        return most_common_sign, average_score

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
            self.label_displayFPS.setText(f'{latest_fps} FPS')
            self.progressBar_fps.setValue(latest_fps)

        if text and scores:
            self.label_recognitionInfo.setText(text[1])
            self.progressBar_hand.setValue(scores[1] * 100)

            if self.checkBox_avg_sign.isChecked():
                self.last_results.append((text[0], scores[0]))
                result_sign, average_score = self.calculate_common_sign_and_average()
            else:
                result_sign, average_score = text[0], scores[0]

            self.label_displaySign.setText(result_sign)
            self.progressBar_1.setValue(average_score * 100)

            if self.checkBox_speak.isChecked():
                self.translate_to_speech(result_sign)
        else:
            self.label_recognitionInfo.setText('Not detected')
            self.label_displaySign.setText('?')
            self.progressBar_1.setValue(0)
            self.progressBar_hand.setValue(0)



    def translate_to_speech(self, data=""):
        """
        Translate the recognized gesture text to speech.

        Args:
            data (str): The recognized gesture text.
         """
        if self.tts_app is not None:
            self.tts_app.speak(data)

    def pushbutton_reset_cap_click(self):
        """
        Reset Camera.
        """
        self.reset_camera()
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