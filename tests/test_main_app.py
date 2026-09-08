import pytest
from PySide6.QtWidgets import QApplication

import main_app
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


def make_window(application, average=False, speak=True):
    window = MainApp()
    window.checkBox_avg_sign.setChecked(average)
    window.checkBox_speak.setChecked(speak)
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

    feed(window, 'A', main_app.SPEECH_STABLE_FRAMES - 1)
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


def test_nothing_is_spoken_while_the_checkbox_is_off(application):
    window = make_window(application, speak=False)

    feed(window, 'A', 5)
    assert window.tts_app.spoken == []

    window.checkBox_speak.setChecked(True)
    feed(window, 'A', 1)

    assert window.tts_app.spoken == ['A']
    window.tts_app = None
    window.close()
