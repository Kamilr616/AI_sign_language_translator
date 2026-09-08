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


class FakeCamera:
    def __init__(self, image):
        self.image = image

    def is_closed(self):
        return False

    def read(self):
        return 1, self.image


class FakeRecognizer:
    def __init__(self):
        self.calls = []

    def recognize_async(self, image, timestamp):
        self.calls.append((image, timestamp))

    def close(self):
        return None


def test_failed_capture_schedules_retry(monkeypatch):
    app = recognizer.GestureRecognizerApp(
        'unused.task', 1, 0.65, 0.65, 0.55, 0.6, FakeCamera(None)
    )
    app.recognizer = FakeRecognizer()
    scheduled = []
    monkeypatch.setattr(
        recognizer.QTimer,
        'singleShot',
        lambda delay, callback: scheduled.append((delay, callback)),
    )

    app.recognize_frame()

    assert len(scheduled) == 1
    assert scheduled[0][0] == app._retry_delay_ms
    app.close()


def test_pending_inference_prevents_duplicate_submission():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    app = recognizer.GestureRecognizerApp(
        'unused.task', 1, 0.65, 0.65, 0.55, 0.6, FakeCamera(frame)
    )
    fake_recognizer = FakeRecognizer()
    app.recognizer = fake_recognizer

    app.recognize_frame()
    app.recognize_frame()

    assert len(fake_recognizer.calls) == 1
    app.close()


def test_fps_waits_for_complete_sample_window(monkeypatch):
    timestamps = iter([100.0, 101.0])
    monkeypatch.setattr(recognizer.time, 'time', lambda: next(timestamps))
    app = recognizer.GestureRecognizerApp(
        'unused.task', 1, 0.65, 0.65, 0.55, 0.6, FakeCamera(None)
    )

    for _ in range(4):
        app.calculate_fps()
    assert app.fps == 0

    app.calculate_fps()
    assert app.fps == 5


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


def make_recognizer_app():
    return recognizer.GestureRecognizerApp(
        'unused.task', 1, 0.65, 0.65, 0.55, 0.6, FakeCamera(None)
    )


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
