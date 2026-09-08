import logging
import os
import sys
from pathlib import Path

from gui import QApplication
from main_app import MainApp
from PySide6.QtGui import QFontDatabase


# Resolved against the application directory, like the pixmaps in gui.ui:
# src/ in source runs and the bundle root in packaged runs.
THEME_PATH = Path('assets') / 'podtekst.qss'
FONT_DIRECTORY = Path('assets') / 'fonts'


def load_fonts(directory=FONT_DIRECTORY):
    """
    Register the bundled fonts (JetBrains Mono, SIL Open Font License) with
    the application, so the theme can use them on any machine.

    Returns:
        int: The number of font files registered.
    """
    registered = 0
    for font_file in sorted(Path(directory).glob('*.ttf')):
        if QFontDatabase.addApplicationFont(str(font_file)) >= 0:
            registered += 1
        else:
            logging.warning("Could not load font: %s", font_file)
    return registered


def load_theme(path=THEME_PATH):
    """
    Read the PodTeksT theme stylesheet; an unreadable file leaves the default
    Qt look rather than stopping the application.

    Returns:
        str: The stylesheet text, empty when it could not be read.
    """
    try:
        return Path(path).read_text(encoding='utf-8')
    except OSError:
        logging.exception("Could not load the theme: %s", path)
        return ''


def main():
    """
    Main function to start the application.
    """
    app_directory = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    os.chdir(app_directory)

    app = QApplication(sys.argv)
    logging.basicConfig(encoding='utf-8', level=logging.INFO)
    load_fonts()
    app.setStyleSheet(load_theme())
    window = MainApp()
    window.start()
    window.show()
    logging.info("Sign language translator application has started!")
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
