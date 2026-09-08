from pathlib import Path

import pytest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

import main
from main_app import MainApp


SRC = Path(__file__).resolve().parents[1] / 'src'


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def test_the_bundled_fonts_register(application):
    assert main.load_fonts(SRC / 'assets' / 'fonts') == 2
    assert QFontDatabase.hasFamily('JetBrains Mono')


def test_the_theme_loads_and_styles_the_window(application):
    theme = main.load_theme(SRC / 'assets' / 'podtekst.qss')

    assert 'QGroupBox' in theme and 'label_displaySign' in theme
    application.setStyleSheet(theme)
    window = MainApp()
    window.show()
    application.processEvents()

    assert window.label_title.text() == 'AI SIGN LANGUAGE TRANSLATOR'
    assert window.label_logoPodteksT.hasScaledContents()
    window.close()
    application.setStyleSheet('')


def test_a_missing_theme_file_is_reported_not_raised(tmp_path):
    assert main.load_theme(tmp_path / 'missing.qss') == ''
    assert main.load_fonts(tmp_path) == 0


def test_the_font_license_ships_with_the_fonts():
    fonts = SRC / 'assets' / 'fonts'

    assert (fonts / 'OFL.txt').read_text(encoding='utf-8').startswith('Copyright 2020 The JetBrains Mono Project Authors')
    assert sorted(f.name for f in fonts.glob('*.ttf')) == ['JetBrainsMono-ExtraBold.ttf', 'JetBrainsMono-Regular.ttf']
