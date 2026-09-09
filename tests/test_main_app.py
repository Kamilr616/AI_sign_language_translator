import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontInfo, QFontMetricsF
from PySide6.QtWidgets import QApplication

import camera as camera_module
import main
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


def test_window_size_constants_match_the_generated_layout(application):
    window = MainApp()

    # main.py scales the interface from these; a regenerated gui.py must not
    # silently move the layout out from under them.
    assert (main.WINDOW_WIDTH_LOGICAL, main.WINDOW_HEIGHT_LOGICAL) == (
        window.width(), window.height()
    )
    window.close()


def test_the_widest_and_deepest_glyphs_fit_inside_the_sign_label(application):
    window = MainApp()
    label = window.label_displaySign
    font = label.font()

    if QFontInfo(font).family() != font.family():
        window.close()
        pytest.skip(f'{font.family()} is not installed on this platform')

    metrics = QFontMetricsF(font)
    # QLabel centres the line box in the label, so the baseline lands here.
    baseline = (label.height() - metrics.height()) / 2.0 + metrics.ascent()

    for glyph in ('Q', 'W', 'M', 'Y', 'B', '?'):
        ink = metrics.tightBoundingRect(glyph)

        assert baseline + ink.top() >= 0, glyph
        assert baseline + ink.top() + ink.height() <= label.height(), glyph
        assert ink.width() <= label.width(), glyph

    window.close()


def test_a_stopped_capture_clears_the_performance_bars(application):
    window = MainApp()
    window.process_result_and_frame(
        None, [], [],
        PipelineMetrics(pipeline_fps=29.7, camera_fps=29.6, inference_ms=17.3, dropped_frames=0),
    )
    window.recognizer_app = StubRecognizer(start_result=False)

    assert window.start_capture() is False

    for bar in (window.progressBar_fps, window.progressBar_camera_fps, window.progressBar_inference):
        assert bar.value() == 0
        assert bar.styleSheet() == ''

    window.recognizer_app = None
    window.close()


def test_settings_fields_only_take_focus_when_they_are_clicked(application):
    window = MainApp()
    window.show()
    fields = (
        window.spinBox_detection,
        window.spinBox_presence,
        window.spinBox_tracking,
        window.spinBox_treshold,
        window.spinBox_volume,
        window.spinBox_ttsRate,
        window.spinBox_camera_width,
        window.spinBox_camera_height,
        window.horizontalSlider_range,
    )

    for field in fields:
        assert field.focusPolicy() == Qt.FocusPolicy.ClickFocus

    QApplication.processEvents()
    focused = QApplication.focusWidget()

    assert focused is None or focused not in fields
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


def test_frame_rate_badness_marks_a_low_rate_as_bad():
    assert main_app.fps_badness(30.0) == 0.0
    assert main_app.fps_badness(25.0) == 0.0
    assert main_app.fps_badness(10.0) == 1.0
    assert main_app.fps_badness(2.0) == 1.0
    assert main_app.fps_badness(17.5) == pytest.approx(0.5)


def test_inference_badness_marks_a_slow_inference_as_bad():
    assert main_app.inference_badness(5.0) == 0.0
    assert main_app.inference_badness(20.0) == 0.0
    assert main_app.inference_badness(50.0) == 1.0
    assert main_app.inference_badness(150.0) == 1.0
    assert main_app.inference_badness(35.0) == pytest.approx(0.5)


def test_confidence_badness_starts_at_the_configured_threshold():
    assert main_app.confidence_badness(0.65, 0.65) == 1.0
    assert main_app.confidence_badness(1.0, 0.65) == 0.0
    assert main_app.confidence_badness(0.825, 0.65) == pytest.approx(0.5)
    assert main_app.confidence_badness(0.4, 0.65) == 1.0
    # A threshold of 1.0 would leave no scale at all, so it is capped.
    assert main_app.confidence_badness(1.0, 1.0) == 0.0
    assert main_app.confidence_badness(0.99, 1.0) == 1.0
    assert main_app.confidence_badness(0.995, 1.0) == pytest.approx(0.5)


def test_bar_text_colour_follows_the_luminance_behind_it():
    assert main_app.text_colour_for('#ffc107') == main_app.DARK_TEXT_COLOUR
    assert main_app.text_colour_for('#4caf50') == main_app.DARK_TEXT_COLOUR
    assert main_app.text_colour_for('#ffffff') == main_app.DARK_TEXT_COLOUR
    assert main_app.text_colour_for('#f44336') == main_app.LIGHT_TEXT_COLOUR
    assert main_app.text_colour_for('#000000') == main_app.LIGHT_TEXT_COLOUR
    assert main_app.text_colour_for(main_app.BAR_GROOVE_COLOUR) == main_app.LIGHT_TEXT_COLOUR


def test_bar_text_is_readable_over_the_groove_on_a_low_reading(application):
    window = MainApp()

    window.update_rate_bar(window.progressBar_hand, 90, 0.0)
    filled = window.progressBar_hand.styleSheet()

    window.update_rate_bar(window.progressBar_hand, 5, 0.0)

    # The same green chunk, but the centred text now lands on the dark groove.
    assert main_app.DARK_TEXT_COLOUR in filled
    assert main_app.LIGHT_TEXT_COLOUR in window.progressBar_hand.styleSheet()
    window.close()


def test_rate_colour_runs_from_green_through_amber_to_red():
    assert main_app.rate_colour(0.0) == '#4caf50'
    assert main_app.rate_colour(0.5) == '#ffc107'
    assert main_app.rate_colour(1.0) == '#f44336'
    assert main_app.rate_colour(-1.0) == '#4caf50'
    assert main_app.rate_colour(2.0) == '#f44336'

    halfway = main_app.rate_colour(0.25)

    assert halfway not in ('#4caf50', '#ffc107')
    assert int(halfway[1:3], 16) > 0x4C
    assert int(halfway[5:7], 16) < 0x50


def test_recognition_rate_widgets_show_all_three_measurements(application):
    window = MainApp()
    metrics = PipelineMetrics(
        pipeline_fps=12.34, camera_fps=28.42, inference_ms=17.34, dropped_frames=5
    )

    window.process_result_and_frame(None, [], [], metrics)

    assert window.label_displayFPS.text() == '12.3 FPS'
    assert window.progressBar_fps.value() == 12
    assert window.label_displayCameraFps.text() == '28.4 FPS'
    assert window.progressBar_camera_fps.value() == 28
    assert window.label_displayInference.text() == '17.3 ms'
    assert window.progressBar_inference.value() == 17
    assert '5' in window.groupBox_cameraRate.toolTip()
    window.close()


def test_no_hand_is_reported_as_none(application):
    window = MainApp()

    window.process_result_and_frame(None, [], [], None)

    assert window.label_recognitionInfo.text() == 'None'
    assert window.label_displaySign.text() == '?'
    window.close()


def test_rate_bars_are_coloured_by_how_bad_the_measurement_is(application):
    window = MainApp()

    window.process_result_and_frame(
        None, [], [],
        PipelineMetrics(pipeline_fps=29.7, camera_fps=29.6, inference_ms=17.3, dropped_frames=0),
    )

    assert '#4caf50' in window.progressBar_fps.styleSheet()
    assert '#4caf50' in window.progressBar_camera_fps.styleSheet()
    assert '#4caf50' in window.progressBar_inference.styleSheet()

    window.process_result_and_frame(
        None, [], [],
        PipelineMetrics(pipeline_fps=6.0, camera_fps=8.0, inference_ms=150.0, dropped_frames=0),
    )

    assert '#f44336' in window.progressBar_fps.styleSheet()
    assert '#f44336' in window.progressBar_camera_fps.styleSheet()
    assert '#f44336' in window.progressBar_inference.styleSheet()
    window.close()


def test_confidence_bars_are_coloured_by_their_score(application):
    window = MainApp()
    window.spinBox_treshold.setValue(65)
    window.spinBox_presence.setValue(65)

    window.process_result_and_frame(None, ['A', 'Right'], [1.0, 1.0], None)

    assert window.progressBar_1.value() == 100
    assert '#4caf50' in window.progressBar_1.styleSheet()
    assert '#4caf50' in window.progressBar_hand.styleSheet()

    window.process_result_and_frame(None, ['A', 'Right'], [0.65, 0.65], None)

    assert '#f44336' in window.progressBar_1.styleSheet()
    assert '#f44336' in window.progressBar_hand.styleSheet()
    window.close()


def test_result_bar_colour_follows_the_threshold_before_a_recognizer_exists(application):
    window = MainApp()
    assert window.recognizer_app is None
    window.spinBox_treshold.setValue(60)

    window.process_result_and_frame(None, ['A', 'Right'], [0.8, 0.9], None)
    lenient = window.progressBar_1.styleSheet()

    window.spinBox_treshold.setValue(80)
    window.process_result_and_frame(None, ['A', 'Right'], [0.8, 0.9], None)
    strict = window.progressBar_1.styleSheet()

    assert '#ffc107' in lenient
    assert '#f44336' in strict
    window.close()


def test_hand_bar_colour_follows_the_presence_before_a_recognizer_exists(application):
    window = MainApp()
    assert window.recognizer_app is None
    window.spinBox_presence.setValue(60)

    window.process_result_and_frame(None, ['A', 'Right'], [0.9, 0.8], None)
    lenient = window.progressBar_hand.styleSheet()

    window.spinBox_presence.setValue(80)
    window.process_result_and_frame(None, ['A', 'Right'], [0.9, 0.8], None)
    strict = window.progressBar_hand.styleSheet()

    assert '#ffc107' in lenient
    assert '#f44336' in strict
    window.close()


def test_bar_ramp_uses_the_threshold_the_recognizer_is_running_with(application, monkeypatch):
    window = MainApp()
    running = StubRecognizer()
    running.score_confidence = 0.60
    running.min_hand_presence_confidence = 0.60
    window.recognizer_app = running
    window.camera_app = object()

    window.process_result_and_frame(None, ['A', 'Right'], [0.8, 0.8], None)
    applied = (window.progressBar_1.styleSheet(), window.progressBar_hand.styleSheet())

    # Typing a stricter threshold changes nothing until the recognizer is rebuilt.
    window.spinBox_treshold.setValue(80)
    window.spinBox_presence.setValue(80)
    window.process_result_and_frame(None, ['A', 'Right'], [0.8, 0.8], None)

    assert (window.progressBar_1.styleSheet(), window.progressBar_hand.styleSheet()) == applied

    candidate = StubRecognizer()

    def build(**kwargs):
        candidate.score_confidence = kwargs['score_confidence']
        candidate.min_hand_presence_confidence = kwargs['min_hand_presence_confidence']
        return candidate

    monkeypatch.setattr(main_app, 'GestureRecognizerApp', build)
    monkeypatch.setattr(candidate, 'create_recognizer', lambda: None, raising=False)

    assert window.reset_recognizer() is True

    window.process_result_and_frame(None, ['A', 'Right'], [0.8, 0.8], None)

    assert '#f44336' in window.progressBar_1.styleSheet()
    assert '#f44336' in window.progressBar_hand.styleSheet()

    window.recognizer_app = None
    window.camera_app = None
    window.close()


def test_no_hand_resets_the_confidence_bars(application):
    window = MainApp()
    window.process_result_and_frame(None, ['A', 'Right'], [0.65, 0.65], None)

    window.process_result_and_frame(None, [], [], None)

    assert window.progressBar_1.value() == 0
    assert window.progressBar_hand.value() == 0
    assert '#4caf50' in window.progressBar_1.styleSheet()
    assert '#4caf50' in window.progressBar_hand.styleSheet()
    window.close()


def test_out_of_range_measurements_are_clamped_to_the_bar(application):
    window = MainApp()

    window.process_result_and_frame(
        None, [], [],
        PipelineMetrics(pipeline_fps=42.0, camera_fps=99.0, inference_ms=150.0, dropped_frames=0),
    )

    assert window.progressBar_fps.value() == 30
    assert window.progressBar_camera_fps.value() == 30
    assert window.progressBar_inference.value() == 100
    window.close()


def test_bar_stylesheet_is_only_rewritten_when_the_colour_changes(application):
    window = MainApp()
    metrics = PipelineMetrics(
        pipeline_fps=29.7, camera_fps=29.6, inference_ms=17.3, dropped_frames=0
    )
    window.process_result_and_frame(None, [], [], metrics)
    applied = []
    window.progressBar_fps.setStyleSheet = lambda sheet: applied.append(sheet)

    window.process_result_and_frame(None, [], [], metrics)

    assert applied == []
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
    assert 'not running' in window.label_displayFPS.text()

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
    assert 'busy' in window.label_displayFPS.text()
    window.recognizer_app = None
    window.close()


def test_camera_settings_dialog_is_skipped_when_capture_will_not_stop(application):
    window = MainApp()
    stub = StubRecognizer(stop_result=False, capture_busy=True)
    window.recognizer_app = stub
    window.camera_app = StubCamera(stub.calls)

    window.pushbutton_camera_settings_click()

    assert stub.calls == ['stop_capture']
    assert 'busy' in window.label_displayFPS.text()
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
        assert window.label_displayFPS.text() == 'camera busy, retry'
    finally:
        workers = camera_module.stranded_workers()
        if worker in workers:
            workers.remove(worker)
        window.recognizer_app = None
        window.camera_app = None
        window.close()
