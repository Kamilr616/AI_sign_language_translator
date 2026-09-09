import pytest

import camera as camera_module
import main


class NeverFinishingWorker:
    """Capture worker that stays blocked in the camera driver forever."""

    def isRunning(self):
        return True


def test_shutdown_exits_normally_when_no_worker_is_stranded():
    with pytest.raises(SystemExit) as exit_info:
        main.shutdown(3)

    assert exit_info.value.code == 3


def test_shutdown_skips_finalizers_while_a_capture_worker_is_stuck(monkeypatch):
    worker = NeverFinishingWorker()
    camera_module.stranded_workers().append(worker)
    codes = []
    monkeypatch.setattr(main.os, '_exit', lambda code: codes.append(code))

    try:
        main.shutdown(0)
    finally:
        camera_module.stranded_workers().remove(worker)

    assert codes == [0]
