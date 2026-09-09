import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import board
import main_app
from corrector import WordCorrector
from main_app import MainApp


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def test_average_score_uses_only_winning_sign_samples(application):
    window = MainApp()
    window.horizontalSlider_range.setValue(3)
    window.last_results = [("A", 0.8), ("B", 0.7), ("A", 1.0)]

    sign, score = window.calculate_common_sign_and_average()

    assert sign == "A"
    assert score == pytest.approx(0.9)
    window.close()


def test_result_window_discards_oldest_sample(application):
    window = MainApp()
    window.horizontalSlider_range.setValue(3)
    window.last_results = [("A", 0.8), ("B", 0.7), ("A", 1.0), ("C", 0.9)]

    window.calculate_results_length()

    assert window.last_results == [("B", 0.7), ("A", 1.0), ("C", 0.9)]
    window.close()


class InvalidRecognizer:
    def __init__(self, **kwargs):
        self.closed = False

    def create_recognizer(self):
        raise ValueError('invalid model')

    def close(self):
        self.closed = True


def test_invalid_model_keeps_previous_recognizer(application, monkeypatch):
    window = MainApp()
    previous_recognizer = object()
    window.camera_app = object()
    window.recognizer_app = previous_recognizer
    messages = []
    monkeypatch.setattr(main_app, 'GestureRecognizerApp', InvalidRecognizer)
    monkeypatch.setattr(
        main_app.QMessageBox,
        'critical',
        lambda *args: messages.append(args),
    )

    assert window.reset_recognizer() is False
    assert window.recognizer_app is previous_recognizer
    assert len(messages) == 1

    window.recognizer_app = None
    window.camera_app = None
    window.close()


def test_window_scales_the_scene_to_its_size(application):
    window = MainApp()
    width, height = window.design_size.width(), window.design_size.height()
    assert (width, height) == (1920, 1080)
    window.show()

    window.resize(width * 2, height * 2 + window.statusBar().height())
    application.processEvents()
    window.fit_scene()
    doubled = window.scene_view.transform().m11()

    window.resize(width // 2 + 40, height // 2 + 40)
    application.processEvents()
    window.fit_scene()
    halved = window.scene_view.transform().m11()

    assert doubled == pytest.approx(2.0, abs=0.05)
    assert halved == pytest.approx(0.5, abs=0.05)
    assert window.label_displayFrame.size().width() == board.preview_rect(window.layout_rects["camera"])[2]
    window.close()


def test_file_dialog_restores_model_path_after_failed_load(application, monkeypatch):
    window = MainApp()
    original_model = window.model_path
    monkeypatch.setattr(
        main_app.QFileDialog,
        'getOpenFileName',
        lambda *args: ('broken.task', ''),
    )
    monkeypatch.setattr(window, 'reset_recognizer', lambda: False)

    window.open_file_dialog()

    assert window.model_path == original_model
    window.close()


class FakeSpeaker:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)

    def stop(self):
        return False


def make_window(application, average=False, speak=True, words=False, correct=False):
    window = MainApp()
    window.checkBox_avg_sign.setChecked(average)
    window.checkBox_speak.setChecked(speak)
    window.comboBox_speak_unit.setCurrentText(main_app.SPEAK_WORDS if words else 'Letters')
    window.checkBox_correct.setChecked(correct)
    window.corrector = WordCorrector.from_words({'hello': 1000, 'world': 800, 'you': 9000, 'hi': 50})
    window.tts_app = FakeSpeaker()
    return window


def test_no_sign_frame_shows_placeholder_and_is_not_spoken(application):
    window = make_window(application)

    window.process_result_and_frame(None, ['', 'Right'], [0.88, 0.99], 20)

    assert window.label_displaySign.text() == '?'
    assert window.progressBar_1.value() == 0
    assert window.label_recognitionInfo.text() == 'Right'
    assert window.progressBar_hand.value() == 99
    assert window.tts_app.spoken == []
    window.tts_app = None
    window.close()


def test_no_sign_frames_vote_in_the_window(application):
    window = make_window(application, average=True)
    window.horizontalSlider_range.setValue(3)

    window.process_result_and_frame(None, ['A', 'Right'], [0.9, 0.99], 20)
    assert window.label_displaySign.text() == 'A'
    window.process_result_and_frame(None, ['', 'Right'], [0.0, 0.99], 20)
    window.process_result_and_frame(None, ['', 'Right'], [0.0, 0.99], 20)

    assert window.label_displaySign.text() == '?'
    assert window.progressBar_1.value() == 0
    assert window.tts_app.spoken == []
    window.tts_app = None
    window.close()


def feed(window, sign, frames):
    for _ in range(frames):
        if sign is None:
            window.process_result_and_frame(None, [], [], 20)
        else:
            window.process_result_and_frame(None, [sign, 'Right'], [0.9 if sign else 0.0, 0.99], 20)


def test_a_letter_is_spoken_once_after_it_is_stable(application):
    window = make_window(application)

    feed(window, 'A', main_app.STABLE_FRAMES - 1)
    assert window.tts_app.spoken == []
    feed(window, 'A', 10)

    assert window.tts_app.spoken == ['A']
    window.tts_app = None
    window.close()


def test_a_new_stable_letter_is_spoken_but_a_flicker_is_not(application):
    window = make_window(application)

    feed(window, 'A', 3)
    feed(window, 'B', 1)
    feed(window, 'A', 3)
    feed(window, 'B', 3)

    assert window.tts_app.spoken == ['A', 'B']
    window.tts_app = None
    window.close()


def test_resting_the_hand_rearms_the_same_letter(application):
    window = make_window(application)

    feed(window, 'A', 3)
    feed(window, '', 3)
    feed(window, 'A', 3)
    feed(window, None, 3)
    feed(window, 'A', 3)

    assert window.tts_app.spoken == ['A', 'A', 'A']
    window.tts_app = None
    window.close()


def test_toggling_average_sign_clears_the_window(application):
    window = make_window(application, average=True, speak=False)
    window.horizontalSlider_range.setValue(8)

    feed(window, 'A', 4)
    assert len(window.last_results) == 4
    window.checkBox_avg_sign.setChecked(False)
    assert window.last_results == []

    feed(window, 'B', 2)
    assert window.last_results == []
    window.checkBox_avg_sign.setChecked(True)
    feed(window, 'B', 1)

    assert window.last_results == [('B', 0.9)]
    assert window.label_displaySign.text() == 'B'
    window.tts_app = None
    window.close()


def test_shrinking_the_range_below_the_stored_results_clears_them(application):
    window = make_window(application, average=True, speak=False)
    window.horizontalSlider_range.setValue(8)

    feed(window, 'A', 6)
    window.horizontalSlider_range.setValue(4)

    assert window.last_results == []
    window.tts_app = None
    window.close()


def test_nothing_is_spoken_while_the_checkbox_is_off(application):
    window = make_window(application, speak=False)

    feed(window, 'A', 5)
    assert window.tts_app.spoken == []

    window.checkBox_speak.setChecked(True)
    feed(window, 'A', 1)
    assert window.tts_app.spoken == []
    feed(window, 'B', 3)

    assert window.tts_app.spoken == ['B']
    window.tts_app = None
    window.close()


def test_stable_letters_are_written_to_the_text_bar(application):
    window = make_window(application)

    feed(window, 'A', 3)
    feed(window, 'B', 1)
    feed(window, 'A', 3)
    feed(window, 'B', 3)
    feed(window, '', 5)
    feed(window, 'B', 3)

    assert window.label_text.text() == 'ABB'
    assert window.tts_app.spoken == ['A', 'B', 'B']
    window.tts_app = None
    window.close()


def test_a_long_rest_ends_the_word_without_speaking(application):
    window = make_window(application)

    feed(window, 'H', 3)
    feed(window, 'I', 3)
    feed(window, None, main_app.REST_FRAMES_FOR_SPACE)
    feed(window, 'U', 3)

    assert window.label_text.text() == 'HI U'
    assert window.tts_app.spoken == ['H', 'I', 'U']
    window.tts_app = None
    window.close()


def test_clear_button_empties_the_text_bar(application):
    window = make_window(application, speak=False)

    feed(window, 'A', 3)
    assert window.label_text.text() == 'A'
    window.pushButton_clearText.click()

    assert window.label_text.text() == ''
    assert window.composer.text == ''
    window.tts_app = None
    window.close()


def spell(window, word, rest=0):
    for letter in word:
        feed(window, letter, 3)
        feed(window, '', 3)
    feed(window, None, rest)


def test_words_mode_speaks_each_finished_word_once_instead_of_letters(application):
    window = make_window(application, words=True)

    spell(window, 'HI', rest=main_app.REST_FRAMES_FOR_SPACE)
    assert window.tts_app.spoken == ['hi']
    spell(window, 'YOU')
    assert window.tts_app.spoken == ['hi']
    feed(window, None, main_app.REST_FRAMES_FOR_SPACE)

    assert window.tts_app.spoken == ['hi', 'you']
    assert window.label_text.text() == 'HI YOU '
    window.tts_app = None
    window.close()


def test_a_finished_word_is_corrected_in_the_text_bar_and_spoken_corrected(application):
    window = make_window(application, words=True, correct=True)

    spell(window, 'HELLLO', rest=main_app.REST_FRAMES_FOR_SPACE)

    assert window.label_text.text() == 'HELLO '
    assert window.composer.text == 'HELLO '
    assert window.tts_app.spoken == ['hello']
    window.tts_app = None
    window.close()


def test_correction_can_be_switched_off(application):
    window = make_window(application, words=True, correct=False)

    spell(window, 'HELLLO', rest=main_app.REST_FRAMES_FOR_SPACE)

    assert window.label_text.text() == 'HELLLO '
    assert window.tts_app.spoken == ['helllo']
    window.tts_app = None
    window.close()


def test_letters_mode_does_not_speak_the_word(application):
    window = make_window(application, words=False, correct=True)

    spell(window, 'HELLLO', rest=main_app.REST_FRAMES_FOR_SPACE)

    assert window.label_text.text() == 'HELLO '
    assert window.tts_app.spoken == list('HELLLO')
    window.tts_app = None
    window.close()


def test_a_long_rest_moves_the_sentence_to_the_transcript(application):
    window = make_window(application, words=True, correct=True)

    spell(window, 'HELLO', rest=main_app.REST_FRAMES_FOR_SPACE)
    spell(window, 'WROLD', rest=main_app.REST_FRAMES_FOR_SENTENCE)

    assert window.label_text.text() == ''
    assert window.composer.text == ''
    lines = window.plainTextEdit_transcript.toPlainText().splitlines()
    assert len(lines) == 1
    assert lines[0].endswith('] HELLO WORLD')
    assert lines[0].startswith('[') and lines[0][3] == ':' and lines[0][6] == ':'
    assert window.tts_app.spoken == ['hello', 'world']

    feed(window, None, 300)
    assert len(window.plainTextEdit_transcript.toPlainText().splitlines()) == 1
    window.pushButton_clearTranscript.click()
    assert window.plainTextEdit_transcript.toPlainText() == ''
    window.tts_app = None
    window.close()


def test_saving_the_transcript_writes_the_file_with_the_pending_sentence(application, monkeypatch, tmp_path):
    window = make_window(application, speak=False)
    target = tmp_path / 'chat.txt'
    monkeypatch.setattr(main_app.QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))

    spell(window, 'HI', rest=main_app.REST_FRAMES_FOR_SENTENCE)
    spell(window, 'YOU')
    assert window.label_text.text() == 'YOU'

    assert window.save_transcript() is True
    lines = target.read_text(encoding='utf-8').splitlines()
    assert [line[11:] for line in lines] == ['HI', 'YOU']
    assert window.label_text.text() == ''
    window.tts_app = None
    window.close()


def test_a_cancelled_save_dialog_changes_nothing(application, monkeypatch):
    window = make_window(application, speak=False)
    monkeypatch.setattr(main_app.QFileDialog, 'getSaveFileName', lambda *args: ('', ''))

    spell(window, 'HI')
    assert window.save_transcript() is False

    assert window.label_text.text() == 'HI'
    assert window.plainTextEdit_transcript.toPlainText() == ''
    window.tts_app = None
    window.close()


def test_an_unwritable_transcript_path_is_reported(application, monkeypatch, tmp_path):
    window = make_window(application, speak=False)
    messages = []
    monkeypatch.setattr(
        main_app.QFileDialog, 'getSaveFileName', lambda *args: (str(tmp_path / 'missing' / 'chat.txt'), ''))
    monkeypatch.setattr(main_app.QMessageBox, 'critical', lambda *args: messages.append(args))

    assert window.save_transcript() is False
    assert len(messages) == 1
    window.tts_app = None
    window.close()


def test_the_status_bar_suggests_completions_while_a_word_is_spelled(application):
    window = make_window(application, speak=False, correct=True)

    feed(window, 'H', 3)
    assert window.statusBar().currentMessage() == ''
    feed(window, '', 3)
    feed(window, 'E', 3)
    assert window.statusBar().currentMessage() == 'HE: hello'
    feed(window, None, main_app.REST_FRAMES_FOR_SPACE)
    assert window.statusBar().currentMessage() == ''

    feed(window, 'Y', 3)
    feed(window, '', 3)
    feed(window, 'O', 3)
    assert window.statusBar().currentMessage() == 'YO: you'
    window.pushButton_clearText.click()

    assert window.statusBar().currentMessage() == ''
    window.tts_app = None
    window.close()


def test_no_completions_while_correction_is_off(application):
    window = make_window(application, speak=False, correct=False)

    feed(window, 'H', 3)
    feed(window, '', 3)
    feed(window, 'E', 3)

    assert window.statusBar().currentMessage() == ''
    window.tts_app = None
    window.close()


def card_widgets(window):
    return {
        'camera': window.groupBox_6, 'text': window.groupBox_text, 'transcript': window.groupBox_transcript,
        'results': window.groupBox_5, 'settings': window.groupBox, 'author': window.groupBox_10,
    }


def shown(window):
    return {card for card, widget in card_widgets(window).items() if not widget.isHidden()}


def test_the_studio_screen_is_the_default_and_pills_switch_screens(application):
    window = MainApp()

    assert window.screen_name == 'studio'
    assert window.pushButton_screenStudio.isChecked()
    assert shown(window) == set(board.CARDS)

    window.pushButton_screenLive.click()
    assert window.screen_name == 'live'
    assert window.pushButton_screenLive.isChecked() and not window.pushButton_screenStudio.isChecked()
    assert shown(window) == {'camera', 'text', 'results'}
    assert window.groupBox_text.property('overlay') is True
    window.set_screen('studio')
    assert window.groupBox_text.property('overlay') is False
    window.set_screen('live')

    window.step_screen(1)
    assert window.screen_name == 'studio'
    window.step_screen(1)
    assert window.screen_name == 'settings'
    assert shown(window) == {'camera', 'settings', 'author'}
    window.step_screen(1)
    assert window.screen_name == 'live'
    window.step_screen(-1)
    assert window.screen_name == 'settings'
    with pytest.raises(ValueError):
        window.set_screen('gallery')
    window.close()


def test_cards_follow_the_computed_layout(application):
    window = MainApp()
    window.set_screen('studio')

    for card, widget in card_widgets(window).items():
        rect = window.layout_rects[card]
        assert (widget.x(), widget.y(), widget.width(), widget.height()) == rect
    preview = board.preview_rect(window.layout_rects['camera'])
    assert (window.label_displayFrame.width(), window.label_displayFrame.height()) == (preview[2], preview[3])
    assert window.pushButton_clearText.x() + window.pushButton_clearText.width() == window.groupBox_text.width() - 16
    window.close()


def test_view_toggles_hide_cards_and_widen_the_camera(application):
    window = MainApp()
    before = window.groupBox_6.width()

    window._card_actions['results'].setChecked(False)
    window._card_actions['settings'].setChecked(False)
    window._card_actions['author'].setChecked(False)

    assert shown(window) == {'camera', 'text', 'transcript'}
    assert window.groupBox_6.width() > before
    window.set_card_visible('results', True)
    assert window._card_actions['results'].isChecked()
    assert 'results' in shown(window)
    window.close()


def test_hiding_the_interface_moves_the_cards_up_and_escape_brings_it_back(application):
    window = MainApp()
    window.set_screen('live')
    top_with_header = window.groupBox_6.y()

    window.action_interface.setChecked(True)
    assert window.header_visible is False
    assert window.label_title.isHidden() and window.pushButton_view.isHidden()
    assert not window.pushButton_showInterface.isHidden()
    assert window.groupBox_6.y() < top_with_header

    window.leave_fullscreen()
    assert window.header_visible is True
    assert not window.label_title.isHidden()
    assert window.pushButton_showInterface.isHidden()
    assert window.groupBox_6.y() == top_with_header

    window.action_interface.setChecked(True)
    window.pushButton_showInterface.click()
    assert window.header_visible is True and not window.action_interface.isChecked()
    window.close()


def test_a_long_text_is_elided_on_the_left(application):
    window = make_window(application, speak=False)
    window.set_screen('studio')

    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYABCDEFGHIJKLMNOPQRSTUVWXYABCDEFGHIJ':
        feed(window, letter, 3)
        feed(window, '', 3)

    shown_text = window.label_text.text()
    assert shown_text.endswith('HIJ')
    assert len(shown_text) < len(window.composer.text)
    assert shown_text[0] == '\u2026'
    window.tts_app = None
    window.close()


def test_board_keys_work_through_the_scene_view(application):
    window = MainApp()
    window.show()
    application.processEvents()

    QTest.keyClick(window.scene_view, Qt.Key.Key_1)
    assert window.screen_name == 'live'
    QTest.keyClick(window.scene_view, Qt.Key.Key_Right)
    assert window.screen_name == 'studio'
    QTest.keyClick(window.scene_view, Qt.Key.Key_H)
    assert window.header_visible is False
    QTest.keyClick(window.scene_view, Qt.Key.Key_H)
    assert window.header_visible is True
    QTest.keyClick(window.scene_view, Qt.Key.Key_H)
    QTest.keyClick(window.scene_view, Qt.Key.Key_Escape)
    assert window.header_visible is True
    QTest.keyClick(window, Qt.Key.Key_3)
    assert window.screen_name == 'settings'
    window.close()


def test_keys_typed_into_a_spin_box_do_not_switch_screens(application):
    window = MainApp()
    window.show()
    application.processEvents()
    window.set_screen('settings')
    window.spinBox_ttsRate.setFocus()
    application.processEvents()

    QTest.keyClick(window.scene_view, Qt.Key.Key_1)

    assert window.screen_name == 'settings'
    window.close()


def test_m_mutes_the_voice_until_it_is_pressed_again(application):
    window = make_window(application)
    window.show()
    application.processEvents()

    feed(window, 'A', main_app.STABLE_FRAMES + 2)
    assert window.tts_app.spoken == ['A']

    QTest.keyClick(window.scene_view, Qt.Key.Key_M)
    assert window.muted is True
    assert window.pushButton_mute.isChecked() and window.action_mute.isChecked()
    assert window.pushButton_mute.text() == 'MUTED'
    feed(window, 'B', main_app.STABLE_FRAMES + 2)
    assert window.composer.text == 'AB'
    assert window.tts_app.spoken == ['A']

    QTest.keyClick(window.scene_view, Qt.Key.Key_M)
    assert window.muted is False
    assert window.pushButton_mute.text() == 'MUTE'
    feed(window, 'C', main_app.STABLE_FRAMES + 2)
    assert window.tts_app.spoken == ['A', 'C']
    window.tts_app = None
    window.close()


def test_the_mute_pill_and_the_menu_entry_stay_in_step_without_touching_the_settings(application):
    window = make_window(application, words=True)

    window.pushButton_mute.click()
    assert window.muted is True and window.action_mute.isChecked()
    feed(window, 'H', main_app.STABLE_FRAMES + 2)
    feed(window, 'I', main_app.STABLE_FRAMES + 2)
    feed(window, None, main_app.REST_FRAMES_FOR_SPACE)
    assert window.composer.text.strip() == 'HI'
    assert window.tts_app.spoken == []
    assert window.checkBox_speak.isChecked()
    assert window.comboBox_speak_unit.currentText() == main_app.SPEAK_WORDS

    window.action_mute.setChecked(False)
    assert window.muted is False and not window.pushButton_mute.isChecked()
    feed(window, 'Y', main_app.STABLE_FRAMES + 2)
    feed(window, None, main_app.REST_FRAMES_FOR_SPACE)
    assert window.tts_app.spoken == ['y']
    window.tts_app = None
    window.close()


class FakeSignal:
    def disconnect(self):
        return None


class StuckRecognizer:
    """Recognizer whose capture worker never leaves its camera read."""

    def __init__(self):
        self.calls = []
        self.result_ready_signal = FakeSignal()

    def stop_capture(self, timeout=2.0):
        self.calls.append('stop')
        return False

    def close(self, timeout=2.0):
        self.calls.append('close')
        return False

    def recognize_frame(self):
        self.calls.append('start')


class FakeCameraApp:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


def test_camera_reset_is_refused_while_the_worker_is_still_reading(application, monkeypatch):
    window = MainApp()
    window.recognizer_app = StuckRecognizer()
    warnings = []
    monkeypatch.setattr(main_app.QMessageBox, 'warning', lambda *args: warnings.append(args[1:3]))
    monkeypatch.setattr(window, 'reset_camera', lambda: pytest.fail('the camera must not be touched'))

    window.pushbutton_reset_cap_click()

    assert warnings and warnings[0][0] == 'Camera busy'
    assert window.recognizer_app.calls == ['stop']
    window.recognizer_app = None
    window.close()


def test_closing_leaves_the_camera_alone_while_the_worker_is_still_reading(application):
    window = MainApp()
    recognizer = StuckRecognizer()
    camera = FakeCameraApp()
    window.recognizer_app = recognizer
    window.camera_app = camera

    window.close()

    assert recognizer.calls == ['close']
    assert camera.destroyed is False
    assert window.recognizer_app is None and window.camera_app is None
