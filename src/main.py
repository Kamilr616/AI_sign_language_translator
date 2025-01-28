import sys
from main_app import MainApp
from gui import QApplication
import qdarkstyle
from qdarkstyle import DarkPalette


def main():
    """
    Main function to start the application.
    """
    app = QApplication(sys.argv)
    if app:
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside6', palette=DarkPalette))
        window = MainApp()
        window.start()
        window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
