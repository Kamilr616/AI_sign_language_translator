import pytest
from PySide6.QtWidgets import QApplication

import main_app
from main_app import MainApp
from recognizer import PipelineMetrics


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


def test_rate_details_line_reports_camera_rate_and_inference_latency():
    metrics = PipelineMetrics(
        pipeline_fps=12, camera_fps=28.42, inference_ms=17.34, dropped_frames=5
    )

    assert main_app.format_rate_details(metrics) == 'camera 28.4 FPS | inference 17.3 ms'


def test_rate_details_line_marks_missing_samples():
    metrics = PipelineMetrics(
        pipeline_fps=0, camera_fps=0.0, inference_ms=0.0, dropped_frames=0
    )

    assert main_app.format_rate_details(metrics) == 'camera -- FPS | inference -- ms'


def test_recognition_rate_widgets_show_pipeline_and_camera_metrics(application):
    window = MainApp()
    metrics = PipelineMetrics(
        pipeline_fps=12, camera_fps=28.42, inference_ms=17.34, dropped_frames=5
    )

    window.process_result_and_frame(None, [], [], metrics)

    assert window.label_displayFPS.text() == '12 FPS'
    assert window.progressBar_fps.value() == 12
    assert window.label_displayRateDetails.text() == 'camera 28.4 FPS | inference 17.3 ms'
    assert '5' in window.label_displayRateDetails.toolTip()
    window.close()
