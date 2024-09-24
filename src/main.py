import sys
import qdarkstyle
from recognizer import GestureRecognizerApp
from gui import *
from speaker import TextToSpeech


class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        """
        Initialize the main application window and connect UI elements to their respective methods.
        """
        super(MainApp, self).__init__()
        self.setupUi(self)

        self.recognizer_app = None
        self.tts_app = None
        self.checkbox_1_flag = False

        # Connect UI elements to their respective methods
        self.checkBox.stateChanged.connect(self.checkbox_change)
        self.startButton.clicked.connect(self.button2_click())
        self.pushButton3.clicked.connect(self.reset_recognizer)
        self.pushButton4.clicked.connect(self.reset_tts)
        self.pushButton2.clicked.connect(self.button1_click)

    def reset_tts(self):
        """
        Reset the text-to-speech engine with new settings.
        """
        if self.tts_app is not None:
            self.tts_app.stop()

        self.tts_app = TextToSpeech(
            rate=self.spinBox5.value(),
            volume=(self.spinBox4.value() / 100.0))

    def reset_recognizer(self):
        """
        Reset the gesture recognizer with new settings.
        """
        if self.recognizer_app is not None:
            self.recognizer_app.result_ready_signal.disconnect()
            self.recognizer_app.close()

        self.recognizer_app = GestureRecognizerApp(
            model='../models/gesture_recognizer_asl_mp.task',
            num_hands=1,
            min_hand_detection_confidence=(self.spinBox1.value() / 100.0),
            min_hand_presence_confidence=(self.spinBox2.value() / 100.0),
            min_tracking_confidence=(self.spinBox3.value() / 100.0),
            score_treshold=(self.spinBox6.value() / 100.0),
            camera_id=0,
            width=640,
            height=480
        )
        self.recognizer_app.result_ready_signal.connect(self.update_frame)
        self.recognizer_app.start()
        self.recognizer_app.recognize_frame()

    def start(self):
        """
        Start the gesture recognizer application if not already started.
        """
        if self.recognizer_app is None:
            self.reset_recognizer()

        if self.tts_app is None:
            self.reset_tts()

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
            self.label.setPixmap(frame)

        if latest_fps:
            self.label_9.setText(f'{latest_fps:.1f} FPS')

        if text and scores:
            self.label2.setText(f'Sign: {text[0]} ({scores[0]:.0%}) - Hand: {text[1]} ({scores[1]:.0%})')
            self.label_7.setText(text[0])
            self.progressBar.setValue(scores[0] * 100)

            if self.checkbox_1_flag:
                self.translate_to_speech(text[0])
        else:
            self.label2.setText('No info')
            self.label_7.setText('-')
            self.progressBar.setValue(0)

    def translate_to_speech(self, data):
        """
        Translate the recognized gesture text to speech.

        Args:
            data (str): The recognized gesture text.
        """
        if self.tts_app is not None:
            self.tts_app.speak(data)

    def checkbox_change(self):
        """
        Toggle the auto mode for text-to-speech.
        """
        self.checkbox_1_flag = not self.checkbox_1_flag

    def button1_click(self):
        """
        Manually trigger text-to-speech translation.
        """
        self.translate_to_speech(self.label2.text())

    def button2_click(self):
        """
        Placeholder for future functionality.
        """
        pass

    def closeEvent(self, event):
        """
        Release resources when closing the application.

        Args:
            event (QCloseEvent): The close event.
        """
        if self.recognizer_app is not None:
            self.recognizer_app.result_ready_signal.disconnect()
            self.recognizer_app.close()
            self.recognizer_app = None

        if self.tts_app is not None:
            self.tts_app.stop()
            self.tts_app = None

        super().closeEvent(event)


def main():
    """
    Main function to start the application.
    """
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyside6())
    window = MainApp()
    window.start()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
