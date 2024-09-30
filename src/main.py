import sys
import qdarkstyle
from main_app import MainApp
from gui import QApplication

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