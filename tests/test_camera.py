import threading
import time

import pytest

import camera as camera_module
from camera import CameraApp, CameraWorker, LatestFrameBuffer


class FakeCapture:
    def __init__(self):
        self.released = False
        self.properties = []
        self.opened = []

    def isOpened(self):
        return not self.released

    def release(self):
        self.released = True

    def open(self, fd, camera_driver=None):
        self.opened.append((fd, camera_driver))
        return True

    def set(self, prop, value):
        self.properties.append((prop, value))
        return True


def forget(worker):
    """Remove a stub worker from the leaked list, which prunes itself."""
    workers = camera_module.stranded_workers()
    if worker in workers:
        workers.remove(worker)


class StrandedWorkerStub:
    """Stands in for a capture worker that never finished."""

    def __init__(self, camera):
        self.camera = camera
        self.running = True
        self.waited = []

    def isRunning(self):
        return self.running

    def is_reading(self, camera):
        return self.running and camera is self.camera

    def wait(self, timeout):
        self.waited.append(timeout)
        return not self.running


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


class BlockingCamera:
    """Fake camera whose read() blocks until it is released."""

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.reads = 0

    def is_closed(self):
        return False

    def read(self):
        self.reads += 1
        self.entered.set()
        self.release.wait(10.0)
        return self.reads * 1_000_000, f"frame-{self.reads}"


class ExplodingCamera:
    """Fake camera whose read() always fails."""

    def __init__(self):
        self.reads = 0

    def is_closed(self):
        return False

    def read(self):
        self.reads += 1
        raise RuntimeError("camera exploded")


def test_destroy_is_safe_when_called_more_than_once():
    camera = CameraApp.__new__(CameraApp)
    camera.cap = FakeCapture()

    camera.destroy()
    camera.destroy()

    assert camera.is_closed()


def test_camera_is_left_alone_while_a_stranded_worker_reads_it():
    camera = CameraApp.__new__(CameraApp)
    capture = FakeCapture()
    camera.cap = capture
    worker = StrandedWorkerStub(camera)
    camera_module.stranded_workers().append(worker)

    try:
        camera.destroy()
        assert capture.released is False
        assert camera.is_closed() is False

        assert camera.open(0) is False
        assert capture.opened == []
        assert capture.released is False

        camera.configure(width=640, height=480)
        assert capture.properties == []

        camera.settings()
        assert capture.properties == []

        worker.running = False
        camera.destroy()
        assert capture.released is True
    finally:
        forget(worker)


def test_stranded_worker_running_reports_leaked_threads():
    camera = CameraApp.__new__(CameraApp)
    worker = StrandedWorkerStub(camera)

    assert camera_module.stranded_worker_running() is False

    camera_module.stranded_workers().append(worker)
    try:
        assert camera_module.stranded_worker_running() is True
        assert camera_module.stranded_workers() == [worker]
        worker.running = False
        assert camera_module.stranded_worker_running() is False
        assert camera_module.stranded_workers() == []
        assert worker.waited == [0]
    finally:
        forget(worker)


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


def test_worker_camera_fps_forgets_intervals_outside_the_window():
    clock = iter([0.0, 1.0, 2.0, 2.1, 2.2])
    camera = TickingCamera(delay=0)
    worker = CameraWorker(camera, fps_window=3, clock=lambda: next(clock))

    for _ in range(5):
        worker.capture_once()

    # Only the last three intervals (1.0, 0.1, 0.1) may be averaged.
    assert worker.camera_fps == pytest.approx(3 / 1.2)


def test_worker_stop_is_safe_before_start_and_supports_restart():
    camera = TickingCamera(delay=0.005)
    worker = CameraWorker(camera)

    assert worker.stop(timeout=1.0) is True

    assert worker.start() is True
    assert worker.start() is True
    assert worker.stop(timeout=5.0) is True
    assert worker.start() is True
    assert worker.stop(timeout=5.0) is True
    assert worker.isRunning() is False


def test_worker_can_restart_after_a_stop_that_timed_out():
    camera = BlockingCamera()
    worker = CameraWorker(camera)

    assert worker.start() is True
    assert camera.entered.wait(5.0) is True

    assert worker.stop(timeout=0.1) is False

    # The driver still holds read(); restarting must fail at once instead of
    # blocking the GUI thread for another stop timeout.
    asked_at = time.monotonic()
    assert worker.start() is False
    assert time.monotonic() - asked_at < 0.5
    assert worker.isRunning() is True

    camera.release.set()
    camera.entered.clear()

    deadline = time.monotonic() + 5.0
    restarted = worker.start()
    while not restarted and time.monotonic() < deadline:
        time.sleep(0.01)
        restarted = worker.start()

    assert restarted is True
    assert camera.entered.wait(5.0) is True

    assert worker.stop(timeout=5.0) is True
    assert camera.reads >= 2


def test_worker_reports_which_camera_it_is_reading():
    camera = BlockingCamera()
    another_camera = TickingCamera(delay=0)
    worker = CameraWorker(camera)

    assert worker.is_reading(camera) is False

    worker.start()
    assert camera.entered.wait(5.0) is True

    assert worker.is_reading(camera) is True
    assert worker.is_reading(another_camera) is False

    camera.release.set()
    assert worker.stop(timeout=5.0) is True
    assert worker.is_reading(camera) is False


def test_worker_keeps_capturing_after_a_read_error():
    camera = ExplodingCamera()
    worker = CameraWorker(camera, idle_delay=0.001)

    worker.start()
    deadline = time.monotonic() + 5.0
    while camera.reads < 3 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert worker.stop(timeout=5.0) is True
    assert camera.reads >= 3
