import pytest
from PySide6.QtWidgets import QApplication

import camera as camera_module
import main_app
from camera import CameraApp
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


def test_smoothing_starts_off_with_the_result_window_disabled(application):
    window = MainApp()

    assert window.pushButton_smoothing.isChecked() is False
    assert window.pushButton_smoothing.text() == "OFF"
    assert window.horizontalSlider_range.isEnabled() is False
    assert window.label_range.isEnabled() is False
    assert window.label_range_value.isEnabled() is False
    window.close()


def test_enabling_smoothing_labels_the_button_and_enables_the_result_window(application):
    window = MainApp()

    window.pushButton_smoothing.setChecked(True)

    assert window.pushButton_smoothing.text() == "ON"
    assert window.horizontalSlider_range.isEnabled() is True
    assert window.label_range.isEnabled() is True
    assert window.label_range_value.isEnabled() is True

    window.pushButton_smoothing.setChecked(False)

    assert window.pushButton_smoothing.text() == "OFF"
    assert window.horizontalSlider_range.isEnabled() is False
    assert window.label_range.isEnabled() is False
    window.close()


def test_disabling_smoothing_clears_the_result_window(application):
    window = MainApp()
    window.pushButton_smoothing.setChecked(True)
    window.last_results = [("A", 1.0), ("A", 1.0)]
    window.last_results_length = 2

    window.pushButton_smoothing.setChecked(False)

    assert window.last_results == []
    assert window.last_results_length == 0
    window.close()


def test_window_size_is_reported_with_its_unit(application):
    window = MainApp()

    assert window.horizontalSlider_range.minimum() == 2
    assert window.horizontalSlider_range.maximum() == 32
    assert window.label_range_value.text() == "15 results"

    window.horizontalSlider_range.setValue(7)

    assert window.label_range_value.text() == "7 results"
    window.close()


def test_raw_result_is_displayed_when_smoothing_is_off(application):
    window = MainApp()
    window.pushButton_smoothing.setChecked(False)
    window.last_results = [("A", 1.0), ("A", 1.0)]

    window.process_result_and_frame(None, ["B", "Right"], [0.4, 0.9], None)

    assert window.label_displaySign.text() == "B"
    assert window.last_results == [("A", 1.0), ("A", 1.0)]
    window.close()


def test_window_vote_is_displayed_when_smoothing_is_on(application):
    window = MainApp()
    window.pushButton_smoothing.setChecked(True)
    window.last_results = [("A", 1.0), ("A", 1.0)]

    window.process_result_and_frame(None, ["B", "Right"], [0.4, 0.9], None)

    assert window.label_displaySign.text() == "A"
    assert window.last_results == [("A", 1.0), ("A", 1.0), ("B", 0.4)]
    window.close()


class FakeCapture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return not self.released

    def release(self):
        self.released = True


class StrandedWorkerStub:
    def __init__(self, camera):
        self.camera = camera
        self.running = True

    def isRunning(self):
        return self.running

    def is_reading(self, camera):
        return self.running and camera is self.camera

    def wait(self, timeout):
        return not self.running


class StubSignal:
    def connect(self, slot):
        return None

    def disconnect(self):
        return None


class StubRecognizer:
    def __init__(self, start_result=True, close_result=True, stop_result=True,
                 capture_busy=False, calls=None):
        self.calls = [] if calls is None else calls
        self.start_result = start_result
        self.close_result = close_result
        self.stop_result = stop_result
        self.capture_busy = capture_busy
        self.result_ready_signal = StubSignal()

    def stop_capture(self):
        self.calls.append('stop_capture')
        return self.stop_result

    def start_capture(self):
        self.calls.append('start_capture')
        return self.start_result

    def close(self):
        self.calls.append('close')
        return self.close_result


class StubCamera:
    def __init__(self, calls):
        self.calls = calls
        self.destroyed = False

    def settings(self):
        self.calls.append('settings')

    def destroy(self):
        self.destroyed = True


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


def test_camera_reset_stops_capture_before_reopening(application, monkeypatch):
    window = MainApp()
    stub = StubRecognizer()
    window.recognizer_app = stub
    monkeypatch.setattr(
        window, 'reset_camera', lambda: stub.calls.append('reset_camera') or True
    )

    window.pushbutton_reset_cap_click()

    assert stub.calls == ['stop_capture', 'reset_camera', 'start_capture']
    window.recognizer_app = None
    window.close()


def test_camera_settings_dialog_pauses_capture(application):
    window = MainApp()
    stub = StubRecognizer()
    window.recognizer_app = stub
    window.camera_app = StubCamera(stub.calls)

    window.pushbutton_camera_settings_click()

    assert stub.calls == ['stop_capture', 'settings', 'start_capture']
    window.recognizer_app = None
    window.camera_app = None
    window.close()


def test_failed_capture_start_is_reported_in_the_readout(application):
    window = MainApp()
    window.recognizer_app = StubRecognizer(start_result=False)

    assert window.start_capture() is False
    assert 'not running' in window.label_displayRateDetails.text()

    window.recognizer_app = None
    window.close()


def test_close_event_releases_the_camera_after_a_clean_stop(application):
    window = MainApp()
    stub = StubRecognizer(close_result=True)
    camera = StubCamera(stub.calls)
    window.recognizer_app = stub
    window.camera_app = camera

    window.close()

    assert camera.destroyed is True
    assert window.camera_app is None


def test_close_event_keeps_the_camera_when_capture_did_not_stop(application):
    window = MainApp()
    stub = StubRecognizer(close_result=False)
    camera = StubCamera(stub.calls)
    window.recognizer_app = stub
    window.camera_app = camera

    window.close()

    assert camera.destroyed is False
    assert window.camera_app is camera


def test_camera_reset_is_skipped_when_capture_will_not_stop(application, monkeypatch):
    window = MainApp()
    stub = StubRecognizer(stop_result=False, capture_busy=True)
    window.recognizer_app = stub
    monkeypatch.setattr(
        window, 'reset_camera', lambda: stub.calls.append('reset_camera') or True
    )

    window.pushbutton_reset_cap_click()

    assert stub.calls == ['stop_capture']
    assert 'busy' in window.label_displayRateDetails.text()
    window.recognizer_app = None
    window.close()


def test_camera_settings_dialog_is_skipped_when_capture_will_not_stop(application):
    window = MainApp()
    stub = StubRecognizer(stop_result=False, capture_busy=True)
    window.recognizer_app = stub
    window.camera_app = StubCamera(stub.calls)

    window.pushbutton_camera_settings_click()

    assert stub.calls == ['stop_capture']
    assert 'busy' in window.label_displayRateDetails.text()
    window.recognizer_app = None
    window.camera_app = None
    window.close()


def test_close_event_keeps_a_camera_held_by_a_stranded_worker(application):
    window = MainApp()
    camera = CameraApp.__new__(CameraApp)
    capture = FakeCapture()
    camera.cap = capture
    worker = StrandedWorkerStub(camera)
    camera_module.stranded_workers().append(worker)

    try:
        # The current recognizer stops cleanly; the camera is still held by the
        # worker a previous recognizer stranded.
        window.recognizer_app = StubRecognizer(close_result=True)
        window.camera_app = camera

        window.close()

        assert capture.released is False
    finally:
        workers = camera_module.stranded_workers()
        if worker in workers:
            workers.remove(worker)


def test_recognizer_reset_reports_a_camera_a_previous_worker_still_holds(application, monkeypatch):
    window = MainApp()
    camera = CameraApp.__new__(CameraApp)
    camera.cap = FakeCapture()
    # A close() that fails always leaves its worker behind on that camera.
    worker = StrandedWorkerStub(camera)
    camera_module.stranded_workers().append(worker)
    window.camera_app = camera
    window.recognizer_app = StubRecognizer(close_result=False)
    candidate = StubRecognizer()
    monkeypatch.setattr(main_app, 'GestureRecognizerApp', lambda **kwargs: candidate)
    monkeypatch.setattr(candidate, 'create_recognizer', lambda: None, raising=False)

    try:
        assert window.reset_recognizer() is True

        assert 'start_capture' not in candidate.calls
        assert window.label_displayRateDetails.text() == 'camera busy, retry'
    finally:
        workers = camera_module.stranded_workers()
        if worker in workers:
            workers.remove(worker)
        window.recognizer_app = None
        window.camera_app = None
        window.close()
