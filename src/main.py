import sys
import os
from pathlib import Path
from main_app import MainApp
from gui import QApplication
import qdarkstyle
from qdarkstyle import DarkPalette
import logging


def main():
    """
    Main function to start the application.
    """
    app_directory = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    os.chdir(app_directory)

    app = QApplication(sys.argv)
    logging.basicConfig(encoding='utf-8', level=logging.INFO)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside6', palette=DarkPalette))
    window = MainApp()
    window.start()
    window.show()
    logging.info("Sign language translator application has started!")
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
