import sys
import cv2
from PySide6.QtCore import QTimer
from recognizer_oop import GestureRecognizerApp
from gui import *

class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainApp, self).__init__()
        self.nolag = False
        self.setupUi(self)

        # Inicjalizacja GestureRecognizerApp
        self.recognizer_app = GestureRecognizerApp(
            model='../models/gesture_recognizer_asl_mp.task',
            num_hands=1,
            min_hand_detection_confidence=0.75,
            min_hand_presence_confidence=0.75,
            min_tracking_confidence=0.75,
            camera_id=0,
            width=640,
            height=480
        )

        # Timer do aktualizacji klatek wideo
        self.interval = 22

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.setInterval(self.interval)

        self.timer2 = QTimer(self)
        self.timer2.timeout.connect(self.recognize_frame)
        self.timer2.setInterval(self.interval)

        # Podłączenie przycisków do metod start i stop
        self.startButton.clicked.connect(self.start_stream)
        self.stopButton.clicked.connect(self.stop_stream)
        self.checkBox.stateChanged.connect(self.nolag_change)

        self.recognizer_app.initialize_camera()
        self.timer.start()
        self.timer2.start()

    def nolag_change(self):
        self.nolag = not self.nolag

    def recognize_frame(self):
        self.recognizer_app.recognize_frame()

    def start_stream(self):
        """
        Rozpoczęcie strumienia wideo.
        """
        self. interval += 1
        self.timer.setInterval(self. interval)
        print(self.interval)

    def stop_stream(self):
        """
        Zatrzymanie strumienia wideo.
        """
        self. interval -= 1
        self.timer.setInterval(self. interval)
        print(self.interval)

    def update_frame(self):
        """
        Pobieranie i wyświetlanie klatki z rozpoznawania gestów.
        """
        frame, text = self.recognizer_app.get_frame(self.nolag)
        if frame is not None:
            # Konwersja z OpenCV (BGR) do QImage (RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

            # Wyświetlanie w QLabel
            self.label.setPixmap(QPixmap.fromImage(qimg))

        if text is not None:
            self.label2.setText(text)

    def closeEvent(self, event):
        """
        Zwalnianie zasobów przy zamykaniu aplikacji.
        """
        self.recognizer_app.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
