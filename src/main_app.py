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


FPS_GOOD = 25.0
FPS_BAD = 10.0
INFERENCE_GOOD_MS = 20.0
INFERENCE_BAD_MS = 50.0
SCORE_THRESHOLD_MAX = 0.99

RATE_COLOUR_STOPS = ((0x4C, 0xAF, 0x50), (0xFF, 0xC1, 0x07), (0xF4, 0x43, 0x36))
BAR_GROOVE_COLOUR = '#19232d'
DARK_TEXT_COLOUR = '#1b1b1b'
LIGHT_TEXT_COLOUR = '#e7e7e7'


def clamp_unit(value):
    """
    Clamp a number to the 0..1 range the colour scale is defined on.

    Args:
        value (float): The number to clamp.

    Returns:
        float: The number, never below 0.0 and never above 1.0.
    """
    return max(0.0, min(1.0, value))


def rate_colour(badness):
    """
    Pick the bar colour for a measurement, green for good and red for bad.

    The scale runs green - amber - red so that a rate on its way out is visible
    before it is bad, and the three stops are muted enough to stay readable on
    the dark theme.

    Args:
        badness (float): 0.0 for the desirable end of the scale, 1.0 for the
            undesirable one; values outside that range are clamped.

    Returns:
        str: The colour as "#rrggbb".
    """
    good, middle, bad = RATE_COLOUR_STOPS
    badness = clamp_unit(badness)

    if badness <= 0.5:
        start, end, position = good, middle, badness / 0.5
    else:
        start, end, position = middle, bad, (badness - 0.5) / 0.5

    channels = (round(a + (b - a) * position) for a, b in zip(start, end))

    return '#%02x%02x%02x' % tuple(channels)


def text_colour_for(background):
    """
    Pick the text colour that stays readable on a background.

    The bars are coloured by their value, so the text over them cannot have
    one fixed colour: white on amber is barely there, and near-black on the
    dark red is no better.

    Args:
        background (str): The colour the text is drawn over, as "#rrggbb".

    Returns:
        str: A near-black or a near-white, whichever contrasts.
    """
    red, green, blue = (int(background[index:index + 2], 16) / 255.0 for index in (1, 3, 5))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue

    return DARK_TEXT_COLOUR if luminance > 0.5 else LIGHT_TEXT_COLOUR


def confidence_badness(score, threshold):
    """
    Rate a confidence score against the threshold it had to clear.

    Anything below the threshold is not something the user chose to accept,
    so the scale starts there rather than at zero: a score that only just
    cleared the bar is as bad as a shown score gets, and certainty is the
    good end. Both confidence bars are read this way, each against its own
    setting, so moving a threshold moves the colours with it.

    Args:
        score (float): The reported score, 0.0 to 1.0.
        threshold (float): The configured threshold, capped at
            SCORE_THRESHOLD_MAX so the scale never collapses to a point.

    Returns:
        float: 0.0 at a score of 1.0, 1.0 at or below the threshold.
    """
    return clamp_unit((1.0 - score) / (1.0 - min(threshold, SCORE_THRESHOLD_MAX)))


def fps_badness(fps):
    """
    Rate a frame rate: a low one is bad, because frames are being missed.

    Args:
        fps (float): The measured frame rate.

    Returns:
        float: 0.0 at or above FPS_GOOD, 1.0 at or below FPS_BAD.
    """
    return clamp_unit((FPS_GOOD - fps) / (FPS_GOOD - FPS_BAD))


def inference_badness(inference_ms):
    """
    Rate an inference latency: a high one is bad, because the result is late.

    Args:
        inference_ms (float): The measured mean latency in milliseconds.

    Returns:
        float: 0.0 at or below INFERENCE_GOOD_MS, 1.0 at or above INFERENCE_BAD_MS.
    """
    return clamp_unit(
        (inference_ms - INFERENCE_GOOD_MS) / (INFERENCE_BAD_MS - INFERENCE_GOOD_MS)
    )


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
        self.bar_colours = {}

        self.pushButton_resetRecognizer.clicked.connect(self.reset_recognizer)
        self.pushButton_resetTTS.clicked.connect(self.reset_tts)
        self.pushButton_resetCap.clicked.connect(self.pushbutton_reset_cap_click)
        self.pushButton_camera_settings.clicked.connect(self.pushbutton_camera_settings_click)
        self.pushButton_model.clicked.connect(self.open_file_dialog)
        self.horizontalSlider_range.valueChanged.connect(self.update_range)
        self.pushButton_smoothing.toggled.connect(self.update_smoothing_mode)

        self.update_range()
        self.update_smoothing_mode()

    def update_range(self):
        """
        Update the result window label and clear results if necessary.
        """
        self.label_range_value.setText(f'{self.horizontalSlider_range.value()} results')

        if self.last_results_length > self.horizontalSlider_range.value():
            self.last_results.clear()

    def update_smoothing_mode(self, *_):
        """
        Label the smoothing button and enable the result window controls with it.

        The window size only matters while the sliding-window vote runs, so the
        slider and its labels are disabled whenever smoothing is off. Switching
        smoothing off also empties the window, so that switching it back on can
        never vote over samples recognized before the pause.
        """
        enabled = self.pushButton_smoothing.isChecked()

        self.pushButton_smoothing.setText('ON' if enabled else 'OFF')
        self.horizontalSlider_range.setEnabled(enabled)
        self.label_range.setEnabled(enabled)
        self.label_range_value.setEnabled(enabled)

        if not enabled:
            self.last_results.clear()
            self.last_results_length = 0

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

        The capture worker is paused for as long as the modal driver dialog is
        open, so the property page and the capture loop never touch the same
        VideoCapture at the same time.
        """
        if not self.camera_app or not self.stop_capture():
            return

        self.camera_app.settings()
        self.start_capture()

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
            min_hand_presence_confidence=self.configured_hand_threshold(),
            min_tracking_confidence=(self.spinBox_tracking.value() / 100.0),
            score_confidence=self.configured_score_threshold(),
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
        capture_released = True
        if previous_recognizer is not None:
            previous_recognizer.result_ready_signal.disconnect()
            capture_released = previous_recognizer.close() is not False

        self.recognizer_app = candidate
        self.recognizer_app.result_ready_signal.connect(self.process_result_and_frame)

        if capture_released:
            self.start_capture()
        else:
            self.report_capture_stopped(
                "Previous capture worker still holds the camera; not starting a second one"
            )
        return True

    def camera_is_busy(self):
        """
        bool: True while any capture worker still holds the camera.
        """
        if self.recognizer_app is not None and self.recognizer_app.capture_busy:
            return True

        return self.camera_app is not None and camera_is_stranded(self.camera_app)

    def report_capture_stopped(self, reason):
        """
        Log why the pipeline is not capturing and say so in the rate readout.

        A worker that still holds the camera will let go of it eventually, so the
        readout asks for a retry; anything else means no capture is running at
        all and pressing the button again would not help.

        Args:
            reason (str): The message to log.
        """
        logging.error(reason)
        self.label_displayFPS.setText(
            'camera busy, retry' if self.camera_is_busy() else 'camera not running'
        )

        for bar in (self.progressBar_fps, self.progressBar_camera_fps, self.progressBar_inference):
            self.reset_rate_bar(bar)

    def stop_capture(self):
        """
        Stop capturing so the camera can be re-opened, re-configured or released.

        Returns:
            bool: True when nothing reads the camera any more. On False the
            caller must not touch the device: the capture worker is still inside
            the driver and pulling the capture away would kill the process.
        """
        if self.recognizer_app is None:
            return True

        if self.recognizer_app.stop_capture():
            return True

        self.report_capture_stopped("Capture worker did not stop; leaving the camera untouched")
        return False

    def start_capture(self):
        """
        Start capturing on the active recognizer and report a failure.

        Returns:
            bool: True when frames are being captured afterwards.
        """
        if self.recognizer_app is None:
            return False

        if self.recognizer_app.start_capture():
            return True

        self.report_capture_stopped("Could not start the camera capture worker")
        return False

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

    def configured_score_threshold(self):
        """
        float: The classification score threshold selected in the GUI.
        """
        return self.spinBox_treshold.value() / 100.0

    def configured_hand_threshold(self):
        """
        float: The hand presence confidence selected in the GUI.
        """
        return self.spinBox_presence.value() / 100.0

    def score_threshold(self):
        """
        float: The classification score threshold the recognizer is running with.

        The spin boxes only reach the recognizer when it is rebuilt, so the
        colour scale follows the value in force rather than the one being
        typed: a bar that changed colour while a threshold was still being
        chosen would be reporting a rule the pipeline is not applying yet.
        """
        if self.recognizer_app is not None:
            return self.recognizer_app.score_confidence

        return self.configured_score_threshold()

    def hand_threshold(self):
        """
        float: The hand presence confidence the recognizer is running with.

        MediaPipe does not gate the handedness score itself, so the presence
        confidence is what the reading is held against: it is the setting that
        says how sure of the hand the user wants the pipeline to be. Like the
        score threshold, it is read from the running recognizer.
        """
        if self.recognizer_app is not None:
            return self.recognizer_app.min_hand_presence_confidence

        return self.configured_hand_threshold()

    def reset_rate_bar(self, bar):
        """
        Empty one bar and take its colour off.

        Nothing is being measured when the pipeline is not running, so the bar
        goes back to the plain theme colour rather than keeping the last reading
        it happened to be showing, which would go on claiming a rate that no
        longer exists.

        Args:
            bar (QProgressBar): The bar to clear.
        """
        bar.setValue(bar.minimum())
        self.bar_colours.pop(bar.objectName(), None)
        bar.setStyleSheet('')

    def update_rate_bar(self, bar, value, badness):
        """
        Show one measurement on its bar and colour the bar by how bad it is.

        The percentage is drawn centred, over the filled part of the bar on a
        reading above half and over the empty groove below it, so the text
        colour is chosen from whichever of the two it will land on. The
        stylesheet is only re-applied when it actually changes: every result
        would otherwise make Qt re-parse and re-polish the widget on the GUI
        thread, several times a second, for no visible difference.

        Args:
            bar (QProgressBar): The bar to update.
            value (float): The measurement, clamped into the bar's range.
            badness (float): 0.0 for a desirable value, 1.0 for an undesirable one.
        """
        clamped = max(bar.minimum(), min(bar.maximum(), int(round(value))))
        bar.setValue(clamped)

        span = bar.maximum() - bar.minimum()
        filled = (clamped - bar.minimum()) / span if span else 0.0
        colour = rate_colour(badness)
        text = text_colour_for(colour if filled >= 0.5 else BAR_GROOVE_COLOUR)
        sheet = (
            f'QProgressBar {{ color: {text}; }}'
            f'QProgressBar::chunk {{ background-color: {colour}; }}'
        )

        if self.bar_colours.get(bar.objectName()) == sheet:
            return

        self.bar_colours[bar.objectName()] = sheet
        bar.setStyleSheet(sheet)

    def update_recognition_rate(self, metrics):
        """
        Update the three sections of the performance readout.

        The pipeline rate, the camera rate and the inference latency are shown
        separately, because a low pipeline FPS can come either from the camera
        (long exposure in low light) or from the model (slow inference); a single
        number cannot tell them apart. The dropped-frame tooltip is set on the
        Camera group box, so it shows when hovering anywhere over that section,
        not just over a specific label.

        Args:
            metrics (PipelineMetrics): The latest pipeline measurements.
        """
        self.label_displayFPS.setText(f'{metrics.pipeline_fps:.1f} FPS')
        self.update_rate_bar(
            self.progressBar_fps, metrics.pipeline_fps, fps_badness(metrics.pipeline_fps)
        )

        self.label_displayCameraFps.setText(f'{metrics.camera_fps:.1f} FPS')
        self.update_rate_bar(
            self.progressBar_camera_fps, metrics.camera_fps, fps_badness(metrics.camera_fps)
        )

        self.label_displayInference.setText(f'{metrics.inference_ms:.1f} ms')
        self.update_rate_bar(
            self.progressBar_inference,
            metrics.inference_ms,
            inference_badness(metrics.inference_ms),
        )

        self.groupBox_cameraRate.setToolTip(
            'Frames dropped because the pipeline was busy '
            f'(total since start): {metrics.dropped_frames}'
        )

    def process_result_and_frame(self, frame, text, scores, metrics):
        """
        Update the UI with the processed frame and recognized gesture text.

        Args:
            frame (QImage): The processed frame.
            text (list): Recognized gesture text.
            scores (list): Scores of the recognized gestures.
            metrics (PipelineMetrics): The latest pipeline, camera and latency measurements.
        """

        if frame:
            self.label_displayFrame.setPixmap(QPixmap.fromImage(frame))

        if metrics is not None:
            self.update_recognition_rate(metrics)

        if text and scores:
            self.label_recognitionInfo.setText(text[1])
            self.update_rate_bar(
                self.progressBar_hand,
                scores[1] * 100,
                confidence_badness(scores[1], self.hand_threshold()),
            )

            if self.pushButton_smoothing.isChecked():
                self.last_results.append((text[0], scores[0]))
                result_sign, average_score = self.calculate_common_sign_and_average()
            else:
                result_sign, average_score = text[0], scores[0]

            self.label_displaySign.setText(result_sign)
            self.update_rate_bar(
                self.progressBar_1,
                average_score * 100,
                confidence_badness(average_score, self.score_threshold()),
            )

            if self.checkBox_speak.isChecked():
                self.translate_to_speech(result_sign)
        else:
            self.label_recognitionInfo.setText('None')
            self.label_displaySign.setText('?')
            self.update_rate_bar(self.progressBar_1, 0, 0.0)
            self.update_rate_bar(self.progressBar_hand, 0, 0.0)

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

        The capture worker is stopped before the device is re-opened, so the camera
        is never read and re-opened at the same time.
        """
        if not self.stop_capture():
            return

        if self.reset_camera():
            self.start_capture()

    def closeEvent(self, event):
        """
        Release resources when closing the application.

        Args:
            event (QCloseEvent): The close event.
        """
        capture_stopped = True
        if self.recognizer_app is not None:
            if self.recognizer_app.result_ready_signal:
                self.recognizer_app.result_ready_signal.disconnect()
            capture_stopped = self.recognizer_app.close() is not False
            self.recognizer_app = None

        if self.camera_app is not None:
            if capture_stopped:
                self.camera_app.destroy()
                self.camera_app = None
            else:
                logging.error(
                    "Capture worker is still reading; leaving the camera open on exit"
                )

        if self.tts_app is not None:
            self.tts_app.stop()
            self.tts_app = None

        super().closeEvent(event)
