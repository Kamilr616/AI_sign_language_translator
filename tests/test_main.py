import os

import pytest

import camera as camera_module
import main


def test_scale_factor_shrinks_a_window_taller_than_the_work_area():
    assert main.scale_factor_for((1171, 782), (1920, 824), 120) == 0.84
    assert main.scale_factor_for((1171, 782), (1920, 600), 96) == 0.76


def test_scale_factor_shrinks_a_window_wider_than_the_work_area():
    # 1024 / 1171 is tighter than 768 / 782, so the width decides.
    assert main.scale_factor_for((1171, 782), (1024, 768), 96) == 0.87


def test_scale_factor_is_one_when_the_window_already_fits():
    assert main.scale_factor_for((1171, 782), (1920, 1040), 120) == 1.0
    assert main.scale_factor_for((1171, 782), (1171, 782), 96) == 1.0


def test_scale_factor_never_collapses_the_interface():
    assert main.scale_factor_for((1171, 782), (1920, 200), 192) == 0.5


def test_scaling_leaves_a_factor_the_user_set_alone(monkeypatch):
    monkeypatch.setenv('QT_SCALE_FACTOR', '1.5')
    monkeypatch.setattr(main, 'work_area_metrics', lambda: (1920, 400, 120.0))

    main.configure_scaling()

    assert os.environ['QT_SCALE_FACTOR'] == '1.5'


def test_scaling_is_applied_when_the_window_would_not_fit(monkeypatch):
    monkeypatch.setenv('QT_SCALE_FACTOR', '')
    monkeypatch.setattr(main, 'work_area_metrics', lambda: (1920, 824, 120.0))

    main.configure_scaling()

    # 812 logical px of frame at 125%: 824 / 812 / 1.25, rounded down.
    assert os.environ['QT_SCALE_FACTOR'] == '0.81'


def test_scaling_is_skipped_when_the_frame_already_fits(monkeypatch):
    monkeypatch.setenv('QT_SCALE_FACTOR', '')
    monkeypatch.setattr(main, 'work_area_metrics', lambda: (1536, 816, 96.0))

    main.configure_scaling()

    assert os.environ['QT_SCALE_FACTOR'] == ''


def test_scaling_is_skipped_without_screen_metrics(monkeypatch):
    monkeypatch.setenv('QT_SCALE_FACTOR', '')
    monkeypatch.setattr(main, 'work_area_metrics', lambda: None)

    main.configure_scaling()

    assert os.environ['QT_SCALE_FACTOR'] == ''


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
