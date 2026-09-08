import logging
import sys
from datetime import datetime
from pathlib import Path

import board
import cv2
from camera import CameraApp
from composer import DELETE_SIGN, SENTENCE_END, TextComposer
from corrector import WordCorrector
from gui import Ui_MainWindow
from PySide6.QtCore import QEvent, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QAction, QGuiApplication, QPainter, QPixmap
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
)
from recognizer import GestureRecognizerApp
from speaker import SpeakerApp


PROJECT_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
MODEL_DIRECTORY = PROJECT_ROOT / 'models'
MODEL_PATH = str(MODEL_DIRECTORY / 'gesture_recognizer_asl_0.task')
# A letter is written and spoken once it has been displayed for this many consecutive frames.
STABLE_FRAMES = 3
# Resting the hand for this many consecutive frames (about a second) ends the word.
REST_FRAMES_FOR_SPACE = 30
# Resting the hand for this many consecutive frames (about three seconds) ends the
# sentence: the text bar is moved to the transcript and starts empty.
REST_FRAMES_FOR_SENTENCE = 90
# Entry of the speech unit combo box that speaks whole words instead of letters.
SPEAK_WORDS = 'Words'
# Keys of the board: screens, the view menu, the interface and fullscreen.
SCREEN_KEYS = {Qt.Key.Key_1: 'live', Qt.Key.Key_2: 'studio', Qt.Key.Key_3: 'settings'}
# Labels of the view menu entries, by card.
CARD_LABELS = {
    'text': 'Text bar',
    'transcript': 'Transcript',
    'results': 'Results',
    'settings': 'Settings',
    'author': 'Author',
}


class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        """
        Initialize the main application window and connect UI elements to their methods.
        """
        super(MainApp, self).__init__()
        self.setupUi(self)
        self.screen_name = 'studio'
        self.card_visible = {card: True for card in board.TOGGLABLE}
        self.header_visible = True
        self._cards = {
            'camera': self.groupBox_6,
            'text': self.groupBox_text,
            'transcript': self.groupBox_transcript,
            'results': self.groupBox_5,
            'settings': self.groupBox,
            'author': self.groupBox_10,
        }
        self._header_widgets = (
            self.label_title, self.label_subtitle, self.label_patchedBy, self.label_logoPodteksT,
            self.pushButton_screenLive, self.pushButton_screenStudio, self.pushButton_screenSettings,
            self.pushButton_view, self.label_keys, self.line_header,
        )
        self._install_board_controls()
        self._install_scaling_view()

        self.driver_names = {}
        self.camera_app = None
        self.recognizer_app = None
        self.tts_app = None
        self.last_results = []
        self.model_path = MODEL_PATH
        self.last_results_length = 0
        self.composer = TextComposer(
            stable_frames=STABLE_FRAMES,
            rest_frames=REST_FRAMES_FOR_SPACE,
            sentence_frames=REST_FRAMES_FOR_SENTENCE,
        )
        # The dictionary is loaded in start(), on a background thread.
        self.corrector = WordCorrector()

        self.pushButton_clearText.clicked.connect(self.clear_text)
        self.pushButton_saveTranscript.clicked.connect(self.save_transcript)
        self.pushButton_clearTranscript.clicked.connect(self.clear_transcript)
        self.pushButton_resetRecognizer.clicked.connect(self.reset_recognizer)
        self.pushButton_resetTTS.clicked.connect(self.reset_tts)
        self.pushButton_resetCap.clicked.connect(self.pushbutton_reset_cap_click)
        self.pushButton_camera_settings.clicked.connect(self.pushbutton_camera_settings_click)
        self.pushButton_model.clicked.connect(self.open_file_dialog)
        self.horizontalSlider_range.valueChanged.connect(self.update_range)
        self.checkBox_avg_sign.toggled.connect(self.clear_results)
        self.apply_layout()

    def _install_board_controls(self):
        """
        Wire the screen pills, the view menu and the keyboard: 1/2/3 and the
        arrow keys switch screens, V opens the view menu, H hides the
        interface, F toggles fullscreen and Escape leaves it.
        """
        self._screen_pills = {
            'live': self.pushButton_screenLive,
            'studio': self.pushButton_screenStudio,
            'settings': self.pushButton_screenSettings,
        }
        self._pill_group = QButtonGroup(self)
        self._pill_group.setExclusive(True)
        for name, pill in self._screen_pills.items():
            self._pill_group.addButton(pill)
            pill.clicked.connect(lambda checked=False, name=name: self.set_screen(name))

        self.view_menu = QMenu(self)
        self._card_actions = {}
        for card in board.TOGGLABLE:
            action = QAction(CARD_LABELS[card], self)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda checked, card=card: self.set_card_visible(card, checked))
            self.view_menu.addAction(action)
            self._card_actions[card] = action
        self.view_menu.addSeparator()
        self.action_interface = QAction("Hide interface\tH", self)
        self.action_interface.setCheckable(True)
        self.action_interface.setToolTip(
            "SHOW UI in the corner, H or Escape brings the interface back; a right click on the picture opens this menu")
        self.action_interface.toggled.connect(lambda hidden: self.set_header_visible(not hidden))
        self.view_menu.addAction(self.action_interface)
        self.action_fullscreen = QAction("Fullscreen\tF", self)
        self.action_fullscreen.setCheckable(True)
        self.action_fullscreen.toggled.connect(self.set_fullscreen)
        self.view_menu.addAction(self.action_fullscreen)
        self.pushButton_view.clicked.connect(lambda checked=False: self.show_view_menu())
        self.pushButton_showInterface.hide()
        self.pushButton_showInterface.clicked.connect(lambda checked=False: self.set_header_visible(True))

    def show_view_menu(self, position=None):
        """
        Open the view menu: under the VIEW pill, at the given global position
        (right click), or at the window centre when the pill is hidden.
        """
        if position is not None:
            origin = position
        elif self.pushButton_view.isVisible():
            origin = self.pushButton_view.mapToGlobal(self.pushButton_view.rect().bottomLeft())
        else:
            origin = self.mapToGlobal(self.rect().center())
        self.view_menu.popup(origin)

    def handle_board_key(self, event):
        """
        Act on a board key: 1/2/3 and the arrow keys switch screens, V opens
        the view menu, H hides or shows the interface, F toggles fullscreen and
        Escape leaves fullscreen or brings the interface back.

        Returns:
            bool: True when the key was a board key and has been handled.
        """
        if event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier:
            return False
        key = event.key()
        if key in SCREEN_KEYS:
            self.set_screen(SCREEN_KEYS[key])
        elif key == Qt.Key.Key_Left:
            self.step_screen(-1)
        elif key == Qt.Key.Key_Right:
            self.step_screen(1)
        elif key == Qt.Key.Key_V:
            self.show_view_menu()
        elif key == Qt.Key.Key_H:
            self.set_header_visible(not self.header_visible)
        elif key == Qt.Key.Key_F:
            self.set_fullscreen(not self.isFullScreen())
        elif key == Qt.Key.Key_Escape:
            self.leave_fullscreen()
        else:
            return False
        return True

    def _typing_widget_focused(self):
        """True while a spin box, combo box or line edit inside the scene has the focus."""
        item = self._scene.focusItem()
        proxy_widget = getattr(item, 'widget', None)
        embedded = proxy_widget() if callable(proxy_widget) else None
        focused = embedded.focusWidget() if embedded is not None else None
        while focused is not None:
            if isinstance(focused, (QAbstractSpinBox, QComboBox, QLineEdit)):
                return True
            focused = focused.parentWidget()
        return False

    def eventFilter(self, watched, event):
        """
        Board keys arrive at the scene view before the scene (the widgets live
        in a QGraphicsProxyWidget, so window shortcuts would not see them);
        keys typed into a spin box, combo box or line edit are left alone.
        """
        if watched is self.scene_view and event.type() == QEvent.Type.KeyPress:
            if not self._typing_widget_focused() and self.handle_board_key(event):
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        """Board keys also work when the window itself has the focus."""
        if not self.handle_board_key(event):
            super().keyPressEvent(event)

    def set_screen(self, name):
        """Show one of the board's screens: 'live', 'studio' or 'settings'."""
        if name not in board.SCREENS:
            raise ValueError(f"Unknown screen: {name}")
        self.screen_name = name
        pill = self._screen_pills[name]
        if not pill.isChecked():
            pill.setChecked(True)
        self.apply_layout()

    def step_screen(self, step):
        """Move to the previous or next screen, wrapping around."""
        index = (board.SCREENS.index(self.screen_name) + step) % len(board.SCREENS)
        self.set_screen(board.SCREENS[index])

    def set_card_visible(self, card, visible):
        """Switch a card on or off in the view menu; the layout fills the gap."""
        self.card_visible[card] = bool(visible)
        action = self._card_actions[card]
        if action.isChecked() != bool(visible):
            action.setChecked(bool(visible))
        self.apply_layout()

    def set_header_visible(self, visible):
        """Show or hide the header strip; the cards take its space when hidden."""
        self.header_visible = bool(visible)
        if self.action_interface.isChecked() == self.header_visible:
            self.action_interface.setChecked(not self.header_visible)
        for widget in self._header_widgets:
            widget.setVisible(self.header_visible)
        self.pushButton_showInterface.setVisible(not self.header_visible)
        self.pushButton_showInterface.raise_()
        self.apply_layout()

    def set_fullscreen(self, fullscreen):
        """Enter or leave fullscreen."""
        if fullscreen and not self.isFullScreen():
            self.showFullScreen()
        elif not fullscreen and self.isFullScreen():
            self.showNormal()
        if self.action_fullscreen.isChecked() != bool(fullscreen):
            self.action_fullscreen.setChecked(bool(fullscreen))

    def leave_fullscreen(self):
        """Escape: leave fullscreen, or bring the interface back when it is hidden."""
        if self.isFullScreen():
            self.set_fullscreen(False)
        elif not self.header_visible:
            self.set_header_visible(True)

    def apply_layout(self):
        """
        Place the cards for the current screen, view toggles and header state
        (see ``board.compute_layout``), resizing the camera preview, the text
        bar and the transcript to their cards.
        """
        self.layout_rects = board.compute_layout(self.screen_name, self.card_visible, self.header_visible)
        for card, widget in self._cards.items():
            rect = self.layout_rects[card]
            widget.setVisible(rect is not None)
            if rect is not None:
                widget.setGeometry(QRect(*rect))

        camera = self.layout_rects['camera']
        x, y, w, h = board.preview_rect(camera)
        self.label_displayFrame.setGeometry(QRect(x - camera[0], y - camera[1], w, h))

        text = self.layout_rects['text']
        if text is not None:
            width = text[2]
            self.label_text.setGeometry(QRect(16, 36, width - 256, 44))
            self.checkBox_correct.setGeometry(QRect(width - 232, 42, 136, 31))
            self.pushButton_clearText.setGeometry(QRect(width - 88, 40, 72, 34))
            self.refresh_text_bar()
        overlay = text is not None and board.text_overlaid(self.screen_name)
        if self.groupBox_text.property('overlay') != overlay:
            self.groupBox_text.setProperty('overlay', overlay)
            self.groupBox_text.style().unpolish(self.groupBox_text)
            self.groupBox_text.style().polish(self.groupBox_text)
        self.groupBox_text.raise_()

        transcript = self.layout_rects['transcript']
        if transcript is not None:
            width, height = transcript[2], transcript[3]
            self.plainTextEdit_transcript.setGeometry(QRect(16, 36, width - 16 - 104, height - 52))
            self.pushButton_saveTranscript.setGeometry(QRect(width - 88, 40, 72, 32))
            self.pushButton_clearTranscript.setGeometry(QRect(width - 88, 80, 72, 32))

    def _install_scaling_view(self):
        """
        Move the fixed-layout central widget into a QGraphicsView and scale the
        whole scene to the window, so the window can be resized or maximized
        (1440p, high-DPI) and every widget follows, keeping the 16:9 proportions
        of the board canvas.
        """
        content = self.takeCentralWidget()
        self.design_size = QSize(*board.CANVAS)
        content.setFixedSize(self.design_size)

        self._scene = QGraphicsScene(self)
        self._scene.addWidget(content)
        self._scene.setSceneRect(QRectF(0, 0, self.design_size.width(), self.design_size.height()))

        view = QGraphicsView(self._scene, self)
        view.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.installEventFilter(self)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(lambda point: self.show_view_menu(view.mapToGlobal(point)))
        self.scene_view = view
        self.setCentralWidget(view)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setMinimumSize(self.design_size.width() // 2, self.design_size.height() // 2)
        self.resize(self._initial_window_size())

    def _initial_window_size(self):
        """
        Fill about 90% of the available screen, between half and twice the
        design size, so the window is neither tiny on 1440p nor off-screen on
        a small laptop display.
        """
        width, height = self.design_size.width(), self.design_size.height()
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QSize(width, height)
        available = screen.availableGeometry()
        factor = min(available.width() * 0.9 / width, available.height() * 0.85 / height, 2.0)
        factor = max(factor, 0.5)
        return QSize(int(width * factor), int(height * factor) + self.statusBar().sizeHint().height())

    def fit_scene(self):
        """Scale the scene to the current window size, keeping its aspect ratio."""
        self.scene_view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_scene()

    def showEvent(self, event):
        super().showEvent(event)
        self.fit_scene()

    def clear_results(self):
        """
        Forget the smoothing window, so votes from before a pause or a toggle
        of "Average sign" cannot shape the next result.
        """
        self.last_results.clear()
        self.last_results_length = 0

    def update_range(self):
        """
        Update the range label and clear results if necessary.
        """
        self.label_range_value.setText(str(self.horizontalSlider_range.value()))

        if len(self.last_results) > self.horizontalSlider_range.value():
            self.clear_results()

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

        self.corrector.load_async()
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
            self.update_text(result_sign)
        else:
            self.label_recognitionInfo.setText('Not detected')
            self.label_displaySign.setText('?')
            self.progressBar_1.setValue(0)
            self.progressBar_hand.setValue(0)
            self.update_text('')

    def update_text(self, sign):
        """
        Feed the displayed sign to the composer: a letter shown for STABLE_FRAMES
        consecutive frames is written to the text bar once (and spoken once in
        the *Letters* mode), a rest of REST_FRAMES_FOR_SPACE frames ends the
        word, which is then corrected against the dictionary and spoken in the
        *Words* mode, and a rest of REST_FRAMES_FOR_SENTENCE frames moves the
        sentence to the transcript.

        Showing the same letter again after a rest writes it again; single-frame
        flickers are ignored. Spaces and deletions are not spoken.

        Args:
            sign (str): The displayed sign, or an empty string for no sign.
        """
        token = self.composer.feed(sign)
        if token is None:
            return

        if token == SENTENCE_END:
            self.append_transcript(self.composer.last_sentence)
        elif token == ' ':
            self.finish_word()
        elif token != DELETE_SIGN and self.speaks_letters():
            self.translate_to_speech(token)
        self.refresh_text_bar()
        self.show_hints()

    def refresh_text_bar(self):
        """
        Show the composed text in the bar; when it is wider than the bar the
        oldest characters are elided on the left, so the newest letters stay
        visible.
        """
        text = self.composer.text
        available = self.label_text.width() - 2 * self.label_text.margin() - 16
        metrics = self.label_text.fontMetrics()
        if metrics.horizontalAdvance(text) > available:
            text = metrics.elidedText(text, Qt.TextElideMode.ElideLeft, available)
        self.label_text.setText(text)

    def show_hints(self):
        """
        List in the status bar up to three dictionary words that start with the
        word being spelled, while *Correct words* is enabled.
        """
        text = self.composer.text
        word = self.composer.last_word if text and not text.endswith(' ') else ''
        hints = self.corrector.complete(word) if word and self.checkBox_correct.isChecked() else []
        if hints:
            self.statusBar().showMessage(f"{word}: {', '.join(hints)}")
        else:
            self.statusBar().clearMessage()

    def speaks_letters(self):
        """True when every stable letter is to be spoken."""
        return self.checkBox_speak.isChecked() and self.comboBox_speak_unit.currentText() != SPEAK_WORDS

    def speaks_words(self):
        """True when each finished word is to be spoken."""
        return self.checkBox_speak.isChecked() and self.comboBox_speak_unit.currentText() == SPEAK_WORDS

    def finish_word(self):
        """
        Correct the word that has just ended when *Correct words* is enabled,
        then speak it in the *Words* mode. Words are spoken in lower case so
        the voice reads them as words rather than spelling them out.
        """
        word = self.composer.last_word
        if not word:
            return

        if self.checkBox_correct.isChecked():
            corrected = self.corrector.correct(word)
            if corrected != word:
                self.composer.replace_last_word(corrected)
                word = corrected

        if self.speaks_words():
            self.translate_to_speech(word.lower())

    def append_transcript(self, sentence):
        """Add a finished sentence to the transcript with the time it ended."""
        if sentence:
            self.plainTextEdit_transcript.appendPlainText(f"[{datetime.now():%H:%M:%S}] {sentence}")

    def flush_sentence(self):
        """Move the sentence still in the text bar to the transcript."""
        sentence = self.composer.text.strip()
        self.clear_text()
        self.append_transcript(sentence)

    def clear_text(self):
        """
        Empty the text bar and forget the letter being composed.
        """
        self.composer.clear()
        self.label_text.setText('')
        self.statusBar().clearMessage()

    def clear_transcript(self):
        """Empty the transcript (the *Clear* button of the transcript panel)."""
        self.plainTextEdit_transcript.clear()

    def save_transcript(self):
        """
        Save the transcript, including the sentence still in the text bar, to a
        text file chosen by the user.

        Returns:
            bool: True when the file was written.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save transcript", str(Path.home() / 'transcript.txt'), "Text files (*.txt)")
        if not file_path:
            return False

        self.flush_sentence()
        try:
            Path(file_path).write_text(self.plainTextEdit_transcript.toPlainText() + '\n', encoding='utf-8')
        except OSError:
            logging.exception("Could not save the transcript: %s", file_path)
            QMessageBox.critical(self, "Save error", f"Could not save transcript: {Path(file_path).name}")
            return False
        return True

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
