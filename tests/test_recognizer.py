import threading

import numpy as np
import pytest

import camera as camera_module
import recognizer
from recognizer import create_scaled_qimage


def test_scaled_qimage_is_detached_from_source_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    large_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    image = create_scaled_qimage(frame)
    scaled_image = create_scaled_qimage(large_frame)
    frame[:] = 255
    large_frame[:] = 255

    assert (image.width(), image.height()) == (640, 480)
    assert (scaled_image.width(), scaled_image.height()) == (640, 360)
    assert image.pixelColor(0, 0).red() == 0
    assert scaled_image.pixelColor(0, 0).red() == 0


class FakeCamera:
    """Camera stub; the recognizer must never read from it directly any more."""

    def __init__(self, closed=False):
        self.closed = closed

    def is_closed(self):
        return self.closed

    def read(self):
        raise AssertionError("the recognizer must consume frames from the capture worker")


class BlockingCamera:
    """Camera whose read() blocks, so the capture worker cannot be stopped."""

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def is_closed(self):
        return False

    def read(self):
        self.entered.set()
        self.release.wait(10.0)
        return 1_000_000, "frame"


class Clock:
    """Settable monotonic clock."""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


class FakeRecognizer:
    def __init__(self, error=None):
        self.calls = []
        self.error = error
        self.closed = False

    def recognize_async(self, image, timestamp):
        self.calls.append((image, timestamp))
        if self.error is not None:
            raise self.error

    def close(self):
        self.closed = True


class FakeOutputImage:
    def __init__(self, frame):
        self.frame = frame

    def numpy_view(self):
        return self.frame


class FakeResult:
    hand_landmarks = []
    gestures = []
    handedness = []


def build_app(fake_recognizer=None, camera=None):
    app = recognizer.GestureRecognizerApp(
        'unused.task', 1, 0.65, 0.65, 0.55, 0.6, camera or FakeCamera()
    )
    app.recognizer = fake_recognizer if fake_recognizer is not None else FakeRecognizer()
    return app


def frame(size=10):
    return np.zeros((size, size, 3), dtype=np.uint8)


def test_recognize_frame_is_idle_when_no_frame_was_captured(monkeypatch):
    app = build_app()
    scheduled = []
    monkeypatch.setattr(
        recognizer.QTimer,
        'singleShot',
        lambda delay, callback: scheduled.append((delay, callback)),
    )

    app.recognize_frame()

    assert app.recognizer.calls == []
    assert scheduled == []
    app.close()


def test_submission_failure_schedules_retry(monkeypatch):
    app = build_app(FakeRecognizer(error=RuntimeError('boom')))
    scheduled = []
    monkeypatch.setattr(
        recognizer.QTimer,
        'singleShot',
        lambda delay, callback: scheduled.append((delay, callback)),
    )
    app.frames.put(5_000_000, frame())

    app.recognize_frame()

    assert len(scheduled) == 1
    assert scheduled[0][0] == app._retry_delay_ms
    assert app._inference_pending is False
    app.close()


def test_pending_inference_drops_frames_instead_of_queuing_them():
    app = build_app()

    app.frames.put(5_000_000, frame())
    app.recognize_frame()
    app.frames.put(6_000_000, frame())
    app.frames.put(7_000_000, frame())
    app.recognize_frame()

    assert len(app.recognizer.calls) == 1
    assert app.frames.dropped_frames == 1
    assert app.metrics().dropped_frames == 1
    app.close()


def test_timestamps_stay_strictly_increasing_within_a_single_millisecond():
    app = build_app()

    for timestamp_ns in (5_000_000, 5_400_000, 5_900_000, 6_000_000):
        app.frames.put(timestamp_ns, frame())
        app.recognize_frame()
        app._inference_pending = False

    timestamps = [timestamp for _, timestamp in app.recognizer.calls]

    assert timestamps == [5, 6, 7, 8]
    assert all(b > a for a, b in zip(timestamps, timestamps[1:]))
    app.close()


def test_inference_latency_is_measured_between_submission_and_callback(monkeypatch):
    ticks = iter([1.0, 1.020, 2.0, 2.010])
    monkeypatch.setattr(recognizer.time, 'perf_counter', lambda: next(ticks))
    app = build_app()

    for _ in range(2):
        app.frames.put(5_000_000, frame())
        app.recognize_frame()
        submitted_timestamp = app.recognizer.calls[-1][1]
        app.handle_result(FakeResult(), FakeOutputImage(frame(480)), submitted_timestamp)

    assert app.inference_ms == pytest.approx(15.0)
    assert app.metrics().inference_ms == pytest.approx(15.0)
    app.close()


def test_stalled_inference_is_dropped_after_the_deadline(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(recognizer.time, 'perf_counter', clock)
    app = build_app()

    app.frames.put(5_000_000, frame())
    app.recognize_frame()
    assert len(app.recognizer.calls) == 1

    clock.now = recognizer.INFERENCE_TIMEOUT_S - 0.1
    app.frames.put(6_000_000, frame())
    app.recognize_frame()
    assert len(app.recognizer.calls) == 1

    clock.now = recognizer.INFERENCE_TIMEOUT_S + 0.1
    app.frames.put(7_000_000, frame())
    app.recognize_frame()

    assert len(app.recognizer.calls) == 2
    app.close()


def test_late_result_of_an_abandoned_inference_is_ignored(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(recognizer.time, 'perf_counter', clock)
    app = build_app()
    results = []
    app.result_ready_signal.connect(lambda *args: results.append(args))

    app.frames.put(5_000_000, frame())
    app.recognize_frame()

    clock.now = recognizer.INFERENCE_TIMEOUT_S + 0.1
    app.frames.put(6_000_000, frame())
    app.recognize_frame()

    assert [timestamp for _, timestamp in app.recognizer.calls] == [5, 6]

    app.handle_result(FakeResult(), FakeOutputImage(frame(480)), 5)

    assert app._inference_pending is True
    assert app.inference_ms == 0.0
    assert results == []

    clock.now += 0.02
    app.handle_result(FakeResult(), FakeOutputImage(frame(480)), 6)

    assert app._inference_pending is False
    assert app.inference_ms == pytest.approx(20.0)
    assert len(results) == 1
    app.close()


def test_metrics_report_the_camera_rate_of_the_capture_worker():
    app = build_app(camera=FakeCamera(closed=True))
    app.start_capture()
    app._worker._camera_fps = 24.5

    assert app.metrics().camera_fps == pytest.approx(24.5)

    assert app.stop_capture() is True
    assert app.metrics().camera_fps == 0.0

    app.close()
    assert app._worker is None


def test_stop_capture_discards_the_buffered_frame():
    app = build_app(camera=FakeCamera(closed=True))
    app.start_capture()
    app.frames.put(5_000_000, frame())

    assert app.stop_capture() is True
    assert app.frames.take() is None

    app.close()


def test_start_capture_reports_a_worker_that_cannot_start():
    app = build_app(camera=FakeCamera(closed=True))

    assert app.start_capture() is True
    app._worker.start = lambda *args, **kwargs: False

    assert app.start_capture() is False

    del app._worker.start
    app.close()


def test_close_keeps_a_capture_worker_that_refuses_to_stop():
    camera = BlockingCamera()
    app = build_app(camera=camera)
    app.start_capture()
    assert camera.entered.wait(5.0) is True

    assert app.close(timeout=0.1) is False
    assert app._worker is None

    stranded = camera_module.stranded_workers()[-1]
    assert stranded.isRunning() is True

    camera.release.set()
    assert stranded.stop(timeout=5.0) is True
    camera_module.stranded_workers().remove(stranded)


def test_close_stops_the_capture_worker():
    app = build_app(camera=FakeCamera(closed=True))
    app.start_capture()
    worker = app._worker

    app.close()

    assert worker.isRunning() is False
    assert app._closing is True


def test_fps_waits_for_complete_sample_window(monkeypatch):
    timestamps = iter([100.0, 101.0])
    monkeypatch.setattr(recognizer.time, 'monotonic', lambda: next(timestamps))
    app = build_app()

    for _ in range(4):
        app.calculate_fps()
    assert app.fps == 0

    app.calculate_fps()
    assert app.fps == 5
    app.close()
