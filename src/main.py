import sys
from main_app import MainApp
from gui import QApplication
import qdarkstyle
from qdarkstyle import DarkPalette
import logging


def main():
    """
    Main function to start the application.
    """
    app = QApplication(sys.argv)
    logging.basicConfig(encoding='utf-8', level=logging.INFO)
    if app:
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside6', palette=DarkPalette))
        window = MainApp()
        window.start()
        window.show()
        logging.info("Sign language translator application has started!")
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
