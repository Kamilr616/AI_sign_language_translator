import sys
import os
from pathlib import Path
from camera import stranded_worker_running
from main_app import MainApp
from gui import QApplication
import qdarkstyle
from qdarkstyle import DarkPalette
import logging


def shutdown(exit_code):
    """
    Leave the process, skipping finalizers when a capture worker is stuck.

    A capture worker that never returned from the camera driver is deliberately
    leaked, and so is the camera handle it uses. Normal interpreter shutdown
    would tear that thread object down while it is still running and abort the
    process with 0xC0000409, so the process exits right here instead.

    Args:
        exit_code (int): The exit code reported by the Qt event loop.
    """
    if not stranded_worker_running():
        sys.exit(exit_code)

    logging.error(
        "A camera capture worker is still blocked in the camera driver: leaking the camera "
        "handle and exiting without running finalizers"
    )
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


def main():
    """
    Main function to start the application.
    """
    app_directory = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    os.chdir(app_directory)

    app = QApplication(sys.argv)
    logging.basicConfig(encoding='utf-8', level=logging.INFO)
    if app:
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside6', palette=DarkPalette))
        window = MainApp()
        window.start()
        window.show()
        logging.info("Sign language translator application has started!")
    shutdown(app.exec())


if __name__ == '__main__':
    main()
