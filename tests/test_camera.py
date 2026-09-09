import time

import pytest

from camera import CameraApp, CameraWorker, LatestFrameBuffer


class FakeCapture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return not self.released

    def release(self):
        self.released = True


class TickingCamera:
    """Fake camera that hands out a new frame on every read()."""

    def __init__(self, delay=0.001, closed=False, fail_after=None):
        self.delay = delay
        self.closed = closed
        self.fail_after = fail_after
        self.reads = 0

    def is_closed(self):
        return self.closed

    def read(self):
        self.reads += 1
        if self.delay:
            time.sleep(self.delay)
        if self.fail_after is not None and self.reads > self.fail_after:
            return self.reads * 1_000_000, None
        return self.reads * 1_000_000, f"frame-{self.reads}"


def test_destroy_is_safe_when_called_more_than_once():
    camera = CameraApp.__new__(CameraApp)
    camera.cap = FakeCapture()

    camera.destroy()
    camera.destroy()

    assert camera.is_closed()


def test_read_stamps_frames_with_a_monotonic_clock(monkeypatch):
    camera = CameraApp.__new__(CameraApp)
    camera.cap = None
    monkeypatch.setattr(time, "monotonic_ns", lambda: 12345)

    timestamp, frame = camera.read()

    assert (timestamp, frame) == (12345, None)


def test_frame_buffer_keeps_only_the_newest_frame_and_counts_drops():
    buffer = LatestFrameBuffer()

    buffer.put(1, "old")
    buffer.put(2, "newer")
    buffer.put(3, "newest")

    assert buffer.take() == (3, "newest")
    assert buffer.dropped_frames == 2


def test_frame_buffer_take_empties_the_slot():
    buffer = LatestFrameBuffer()
    buffer.put(1, "frame")

    assert buffer.take() == (1, "frame")
    assert buffer.take() is None
    assert buffer.dropped_frames == 0


def test_frame_buffer_clear_discards_without_counting_a_drop():
    buffer = LatestFrameBuffer()
    buffer.put(1, "frame")

    buffer.clear()

    assert buffer.take() is None
    assert buffer.dropped_frames == 0


def test_worker_skips_capture_while_the_camera_is_closed():
    camera = TickingCamera(closed=True)
    worker = CameraWorker(camera)

    assert worker.capture_once() is False
    assert camera.reads == 0
    assert worker.frames.take() is None


def test_worker_ignores_failed_reads():
    camera = TickingCamera(delay=0, fail_after=0)
    worker = CameraWorker(camera)

    assert worker.capture_once() is False
    assert worker.frames.take() is None


def test_worker_camera_fps_is_averaged_over_the_sample_window():
    clock = iter([0.0, 0.05, 0.10, 0.15])
    camera = TickingCamera(delay=0)
    worker = CameraWorker(camera, fps_window=3, clock=lambda: next(clock))

    assert worker.camera_fps == 0.0
    worker.capture_once()
    assert worker.camera_fps == 0.0

    for _ in range(3):
        worker.capture_once()

    assert worker.camera_fps == pytest.approx(20.0)


def test_worker_publishes_the_newest_frame_and_stops_cleanly():
    camera = TickingCamera(delay=0.005)
    worker = CameraWorker(camera)

    worker.start()
    deadline = time.monotonic() + 5.0
    while camera.reads < 3 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert worker.stop(timeout=5.0) is True
    assert worker.isRunning() is False
    assert camera.reads >= 3

    buffered = worker.frames.take()
    assert buffered is not None
    assert buffered[1] == f"frame-{camera.reads}"

    reads_after_stop = camera.reads
    time.sleep(0.05)
    assert camera.reads == reads_after_stop


def test_worker_stop_is_safe_before_start_and_supports_restart():
    camera = TickingCamera(delay=0.005)
    worker = CameraWorker(camera)

    assert worker.stop(timeout=1.0) is True

    worker.start()
    assert worker.stop(timeout=5.0) is True
    worker.start()
    assert worker.stop(timeout=5.0) is True
    assert worker.isRunning() is False
