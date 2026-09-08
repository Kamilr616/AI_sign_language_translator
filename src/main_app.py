from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QMessageBox
from recognizer import GestureRecognizerApp
from gui import *
from speaker import SpeakerApp
from camera import *
import logging
from pathlib import Path
import sys


PROJECT_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
MODEL_DIRECTORY = PROJECT_ROOT / 'models'
MODEL_PATH = str(MODEL_DIRECTORY / 'gesture_recognizer_asl_0.task')
# A letter is spoken once it has been displayed for this many consecutive frames.
SPEECH_STABLE_FRAMES = 3


class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        """
        Initialize the main application window and connect UI elements to their methods.
        """
        super(MainApp, self).__init__()
        self.setupUi(self)

        self.driver_names = {}
        self.camera_app = None
        self.recognizer_app = None
        self.tts_app = None
        self.last_results = []
        self.model_path = MODEL_PATH
        self.last_results_length = 0
        self._speech_candidate = None
        self._speech_stable_frames = 0
        self._last_spoken_sign = None

        self.pushButton_resetRecognizer.clicked.connect(self.reset_recognizer)
        self.pushButton_resetTTS.clicked.connect(self.reset_tts)
        self.pushButton_resetCap.clicked.connect(self.pushbutton_reset_cap_click)
        self.pushButton_camera_settings.clicked.connect(self.pushbutton_camera_settings_click)
        self.pushButton_model.clicked.connect(self.open_file_dialog)
        self.horizontalSlider_range.valueChanged.connect(self.update_range)

    def update_range(self):
        """
        Update the range label and clear results if necessary.
        """
        self.label_range_value.setText(str(self.horizontalSlider_range.value()))

        if self.last_results_length > self.horizontalSlider_range.value():
            self.last_results.clear()

    def calculate_results_length(self):
        """
        Calculate the length of the last results and remove the oldest result if necessary.
        """
        self.last_results_length = len(self.last_results)

        if self.last_results_length > self.horizontalSlider_range.value():
            self.last_results.pop(0)

    def create_drivers_dict(self):
        """
        Create a dictionary of camera drivers and their corresponding names.
        """
        self.driver_names = {
            cv2.CAP_ANY: "Auto",
            cv2.CAP_VFW: "Video for Windows",
            cv2.CAP_V4L: "V4L (Linux)",
            cv2.CAP_V4L2: "V4L2 (Linux)",
            cv2.CAP_FIREWIRE: "FireWire",
            cv2.CAP_FIREWARE: "FireWare",
            cv2.CAP_IEEE1394: "IEEE 1394",
            cv2.CAP_DC1394: "DC 1394",
            cv2.CAP_CMU1394: "CMU 1394",
            cv2.CAP_QT: "QuickTime",
            cv2.CAP_UNICAP: "Unicap",
            cv2.CAP_DSHOW: "DirectShow",
            cv2.CAP_PVAPI: "PvAPI",
            cv2.CAP_OPENNI: "OpenNI",
            cv2.CAP_OPENNI_ASUS: "OpenNI (Asus)",
            cv2.CAP_ANDROID: "Android",
            cv2.CAP_XIAPI: "XIMEA",
            cv2.CAP_AVFOUNDATION: "AV Foundation (Mac)",
            cv2.CAP_GIGANETIX: "Giganetix",
            cv2.CAP_MSMF: "Media Foundation",
            cv2.CAP_WINRT: "Windows RT",
            cv2.CAP_INTELPERC: "Intel Perceptual Computing",
            cv2.CAP_REALSENSE: "Intel RealSense",
            cv2.CAP_OPENNI2: "OpenNI2",
            cv2.CAP_OPENNI2_ASUS: "OpenNI2 (Asus)",
            cv2.CAP_OPENNI2_ASTRA: "OpenNI2 (Astra)",
            cv2.CAP_GPHOTO2: "gPhoto2",
            cv2.CAP_GSTREAMER: "GStreamer",
            cv2.CAP_FFMPEG: "FFMPEG",
            cv2.CAP_IMAGES: "Images",
            cv2.CAP_ARAVIS: "Aravis",
            cv2.CAP_OPENCV_MJPEG: "OpenCV MJPEG",
            cv2.CAP_INTEL_MFX: "Intel MFX",
            cv2.CAP_XINE: "Xine",
            cv2.CAP_UEYE: "uEye",
            cv2.CAP_OBSENSOR: "OB Sensor"
        }

    def populate_camera_drivers(self):
        """
        Populate the camera drivers combo box with available drivers.
        """
        self.comboBox_drivers.clear()
        self.comboBox_drivers.addItem(self.driver_names.get(cv2.CAP_ANY, "Auto"), cv2.CAP_ANY)
        drivers = cv2.videoio_registry.getCameraBackends()

        for driver in drivers:
            if driver == cv2.CAP_ANY:
                continue
            name = self.driver_names.get(driver, f"Unknown ({driver})")
            self.comboBox_drivers.addItem(name, driver)

        default_driver = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        default_index = self.comboBox_drivers.findData(default_driver)
        self.comboBox_drivers.setCurrentIndex(max(default_index, 0))

    def populate_cameras(self):
        """
        Populate the cameras combo box with available cameras.
        """
        cameras = QMediaDevices.videoInputs()
        self.comboBox_cameras.clear()

        for index, cam in enumerate(cameras):
            self.comboBox_cameras.addItem(cam.description(), index)
        self.comboBox_cameras.setCurrentIndex(0)

    def open_file_dialog(self):
        """
        Open a file dialog to select a model file and reset the recognizer with the new model.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Choose model file", str(MODEL_DIRECTORY), "Files .task (*.task)")

        if file_path:
            previous_model_path = self.model_path
            self.model_path = file_path
            if not self.reset_recognizer():
                self.model_path = previous_model_path

    def pushbutton_camera_settings_click(self):
        """
        Open the camera settings dialog.
        """
        if self.camera_app:
            self.camera_app.settings()

    def init_camera(self):
        """
        Initialize the camera application with the selected settings.
        """
        try:
            self.populate_cameras()
            self.populate_camera_drivers()
            camera_id = self.comboBox_cameras.currentData()
            camera_driver = self.comboBox_drivers.currentData()
            self.camera_app = CameraApp(
                fd=0 if camera_id is None else camera_id,
                camera_driver=cv2.CAP_ANY if camera_driver is None else camera_driver,
                width=self.spinBox_camera_width.value(),
                height=self.spinBox_camera_height.value(),
            )
        except Exception:
            logging.exception("Error while initializing camera")

    def reset_camera(self):
        """
        Reset the camera application with new settings and start recognizing frames.
        """
        if self.camera_app is None:
            return False

        try:
            camera_id = self.comboBox_cameras.currentData()
            camera_driver = self.comboBox_drivers.currentData()
            opened = self.camera_app.open(
                fd=0 if camera_id is None else camera_id,
                camera_driver=cv2.CAP_ANY if camera_driver is None else camera_driver,
            )
            self.camera_app.configure(
                width=self.spinBox_camera_width.value(),
                height=self.spinBox_camera_height.value(),
            )
            return opened
        except Exception:
            logging.exception("Error while resetting camera")
            return False

    def reset_tts(self):
        """
        Reset the text-to-speech engine with new settings.
        """
        if self.tts_app is not None:
            self.tts_app.stop()

        self.tts_app = SpeakerApp(
            rate=self.spinBox_ttsRate.value(),
            volume=(self.spinBox_volume.value() / 100.0))

    def reset_recognizer(self):
        """
        Reset the gesture recognizer with new settings.
        """
        if self.camera_app is None:
            return False

        candidate = GestureRecognizerApp(
            model=self.model_path,
            num_hands=1,
            min_hand_detection_confidence=(self.spinBox_detection.value() / 100.0),
            min_hand_presence_confidence=(self.spinBox_presence.value() / 100.0),
            min_tracking_confidence=(self.spinBox_tracking.value() / 100.0),
            score_confidence=(self.spinBox_treshold.value() / 100.0),
            camera=self.camera_app,
        )

        try:
            candidate.create_recognizer()
        except Exception:
            candidate.close()
            logging.exception("Could not load gesture recognizer model: %s", self.model_path)
            QMessageBox.critical(
                self,
                "Model error",
                f"Could not load model: {Path(self.model_path).name}",
            )
            return False

        previous_recognizer = self.recognizer_app
        if previous_recognizer is not None:
            previous_recognizer.result_ready_signal.disconnect()
            previous_recognizer.close()

        self.recognizer_app = candidate
        self.recognizer_app.result_ready_signal.connect(self.process_result_and_frame)
        self.recognizer_app.recognize_frame()
        return True

    def start(self):
        """
        Start the gesture recognizer application if not already started.
        """
        self.create_drivers_dict()

        if not self.camera_app:
            self.init_camera()

        if not self.tts_app:
            self.reset_tts()

        if not self.recognizer_app:
            self.reset_recognizer()

        self.update_range()

    def calculate_common_sign_and_average(self):
        """
        Calculate the most common sign and the average score for that sign.

        Returns:
            tuple: A tuple containing the most common sign (str) and its average score (float).
        """
        self.calculate_results_length()

        if self.last_results_length < 1:
            return "", 0.0

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

    def process_result_and_frame(self, frame, text, scores, latest_fps):
        """
        Update the UI with the processed frame and recognized gesture text.

        Args:
            frame (QImage): The processed frame.
            text (list): Recognized gesture text.
            scores (list): Scores of the recognized gestures.
            latest_fps (int): The latest frames per second (FPS) value.
        """

        if frame:
            self.label_displayFrame.setPixmap(QPixmap.fromImage(frame))

        if latest_fps:
            self.label_displayFPS.setText(f'{latest_fps} FPS')
            self.progressBar_fps.setValue(latest_fps)

        if text and scores:
            self.label_recognitionInfo.setText(text[1])
            self.progressBar_hand.setValue(scores[1] * 100)
            # An empty sign means the hand is visible but no sign passed the
            # threshold; it votes in the window like any other outcome.
            sign = text[0]
            score = scores[0] if sign else 0.0

            if self.checkBox_avg_sign.isChecked():
                self.last_results.append((sign, score))
                result_sign, average_score = self.calculate_common_sign_and_average()
            else:
                result_sign, average_score = sign, score

            self.label_displaySign.setText(result_sign or '?')
            self.progressBar_1.setValue(average_score * 100)
            self.update_speech(result_sign)
        else:
            self.label_recognitionInfo.setText('Not detected')
            self.label_displaySign.setText('?')
            self.progressBar_1.setValue(0)
            self.progressBar_hand.setValue(0)
            self.update_speech('')

    def update_speech(self, sign):
        """
        Speak a letter once, after it has been displayed for SPEECH_STABLE_FRAMES
        consecutive frames, instead of repeating it on every frame.

        A stable "no sign" (hand gone or resting) re-arms the last letter, so
        showing it again speaks it again. Single-frame flickers are ignored.

        Args:
            sign (str): The displayed sign, or an empty string for no sign.
        """
        if sign != self._speech_candidate:
            self._speech_candidate = sign
            self._speech_stable_frames = 0
        self._speech_stable_frames += 1

        if self._speech_stable_frames < SPEECH_STABLE_FRAMES:
            return

        if not sign:
            self._last_spoken_sign = None
        elif sign != self._last_spoken_sign and self.checkBox_speak.isChecked():
            self._last_spoken_sign = sign
            self.translate_to_speech(sign)

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

        The capture worker is paused while the device is reopened and restarted
        afterwards; if the device could not be opened the worker keeps polling,
        so a later successful reset resumes recognition on its own.
        """
        if self.recognizer_app is not None:
            self.recognizer_app.stop_capture()
        self.reset_camera()
        if self.recognizer_app is not None:
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
