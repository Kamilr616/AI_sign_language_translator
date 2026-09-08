import threading
import time

import numpy as np

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


FRAME = np.zeros((10, 10, 3), dtype=np.uint8)


class FakeCamera:
    """Camera returning a scripted sequence of (timestamp_ns, image) pairs.

    After the script runs out it keeps returning frames 33 ms apart, or ``None``
    frames when ``then_fail`` is set.
    """

    def __init__(self, script=(), then_fail=False):
        self.script = list(script)
        self.then_fail = then_fail
        self.reads = 0
        self._next_timestamp = 1_000_000_000
        self._lock = threading.Lock()

    def is_closed(self):
        return False

    def read(self):
        with self._lock:
            self.reads += 1
            if self.script:
                return self.script.pop(0)
            self._next_timestamp += 33_000_000
            if self.then_fail:
                return self._next_timestamp, None
            return self._next_timestamp, FRAME.copy()


class FakeRecognizer:
    def __init__(self):
        self.calls = []

    def recognize_async(self, image, timestamp):
        self.calls.append(timestamp)

    def close(self):
        return None


class FakeCategory:
    def __init__(self, category_name, score, index=0):
        self.category_name = category_name
        self.score = score
        self.index = index


class FakeLandmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.z = 0.0


class FakeResult:
    def __init__(self, gesture_categories):
        self.hand_landmarks = [[FakeLandmark(0.1 + 0.04 * i, 0.5) for i in range(21)]]
        self.handedness = [[FakeCategory('Right', 0.99)]]
        self.gestures = [gesture_categories]


class FakeImage:
    def __init__(self, frame):
        self._frame = frame

    def numpy_view(self):
        return self._frame


def make_recognizer_app(camera=None):
    return recognizer.GestureRecognizerApp(
        'unused.task', 1, 0.65, 0.65, 0.55, 0.6, camera or FakeCamera()
    )


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def test_capture_worker_submits_strictly_increasing_millisecond_timestamps():
    # Four frames, three of them inside the same millisecond, then no more frames.
    camera = FakeCamera(
        script=[(5_000_000_000, FRAME), (5_000_300_000, FRAME), (5_000_600_000, FRAME), (5_001_000_000, FRAME)],
        then_fail=True,
    )
    app = make_recognizer_app(camera)
    fake = FakeRecognizer()
    app.recognizer = fake
    # Complete every inference immediately, the way MediaPipe's callback does.
    original = fake.recognize_async
    fake.recognize_async = lambda image, ts: (original(image, ts), app.handle_result(FakeResult([]), FakeImage(FRAME.copy()), ts))

    app.recognize_frame()
    assert wait_until(lambda: len(fake.calls) >= 4)
    app.close()

    assert fake.calls == [5000, 5001, 5002, 5003]
    assert app._capture_thread is None


def test_pending_inference_drops_frames_until_the_result_arrives():
    camera = FakeCamera()
    app = make_recognizer_app(camera)
    fake = FakeRecognizer()
    app.recognizer = fake

    app.recognize_frame()
    assert wait_until(lambda: len(fake.calls) == 1)
    assert wait_until(lambda: camera.reads >= 5)
    assert len(fake.calls) == 1

    app.handle_result(FakeResult([]), FakeImage(FRAME.copy()), fake.calls[-1])
    assert wait_until(lambda: len(fake.calls) == 2)
    app.close()


def test_result_watchdog_resumes_submission_after_a_lost_callback():
    camera = FakeCamera()
    app = make_recognizer_app(camera)
    app._pending_timeout_s = 0.1
    fake = FakeRecognizer()
    app.recognizer = fake

    app.recognize_frame()
    assert wait_until(lambda: len(fake.calls) >= 2, timeout=1.5)
    app.close()


def test_failed_captures_keep_retrying_without_stopping_the_worker():
    failures = [(1_000_000_000 + i, None) for i in range(3)]
    camera = FakeCamera(script=failures)
    app = make_recognizer_app(camera)
    app._retry_delay_s = 0.005
    fake = FakeRecognizer()
    app.recognizer = fake

    app.recognize_frame()
    assert wait_until(lambda: len(fake.calls) >= 1)
    assert camera.reads >= 4
    app.close()


def test_recognize_frame_starts_a_single_worker():
    camera = FakeCamera()
    app = make_recognizer_app(camera)
    app.recognizer = FakeRecognizer()

    app.recognize_frame()
    first = app._capture_thread
    app.recognize_frame()

    assert app._capture_thread is first
    assert first.is_alive()
    app.close()


def test_close_stops_the_capture_worker():
    camera = FakeCamera()
    app = make_recognizer_app(camera)
    app.recognizer = FakeRecognizer()

    app.recognize_frame()
    assert wait_until(lambda: camera.reads >= 1)
    thread = app._capture_thread
    app.close()

    assert not thread.is_alive()
    reads = camera.reads
    time.sleep(0.05)
    assert camera.reads == reads


def test_fps_waits_for_complete_sample_window(monkeypatch):
    timestamps = iter([100.0, 101.0])
    monkeypatch.setattr(recognizer.time, 'time', lambda: next(timestamps))
    app = make_recognizer_app()

    for _ in range(4):
        app.calculate_fps()
    assert app.fps == 0

    app.calculate_fps()
    assert app.fps == 5


def test_named_gesture_is_reported_with_handedness():
    app = make_recognizer_app()
    frame = np.zeros((48, 64, 3), dtype=np.uint8)

    _, text, scores = app.process_recognition_result(frame, FakeResult([FakeCategory('A', 0.9)]))

    assert text == ['A', 'Right']
    assert scores == [0.9, 0.99]


def test_background_category_is_reported_as_no_sign():
    app = make_recognizer_app()
    frame = np.zeros((48, 64, 3), dtype=np.uint8)

    _, text, scores = app.process_recognition_result(
        frame, FakeResult([FakeCategory('', 0.88, index=-1)])
    )
    _, empty_text, empty_scores = app.process_recognition_result(frame, FakeResult([]))

    assert text == ['', 'Right']
    assert scores == [0.0, 0.99]
    assert empty_text == ['', 'Right']
    assert empty_scores == [0.0, 0.99]
