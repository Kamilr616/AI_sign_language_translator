import sys
import os
import math
from pathlib import Path
from camera import stranded_worker_running
from main_app import MainApp
from gui import QApplication
import qdarkstyle
from qdarkstyle import DarkPalette
import logging


WINDOW_WIDTH_LOGICAL = 1171
WINDOW_HEIGHT_LOGICAL = 782
WINDOW_FRAME_HEIGHT_LOGICAL = 30
SPI_GETWORKAREA = 0x0030
MIN_SCALE_FACTOR = 0.5


def scale_factor_for(window_size_logical, work_area_size_px, dpi):
    """
    Work out the interface scale at which the fixed window fits the screen.

    The window is laid out at a fixed size, so on a display whose work area is
    smaller than that once the system scaling is applied, the window would
    simply be cut off. Scaling the whole interface down by the ratio that is
    missing is what makes it fit; both extents are measured and the tighter one
    decides, and the factor is rounded down to two decimals so a rounding error
    cannot leave a row of pixels off-screen.

    Args:
        window_size_logical (tuple): The window (width, height) as laid out, in
            logical pixels.
        work_area_size_px (tuple): The (width, height) of the screen work area,
            in the same pixels the DPI below is reported in.
        dpi (float): The system DPI; 96 means no system scaling.

    Returns:
        float: 1.0 when the window already fits, otherwise the factor that makes
        it fit, never below MIN_SCALE_FACTOR.
    """
    device_scale = dpi / 96.0

    if device_scale <= 0:
        return 1.0

    missing = [
        available / extent / device_scale
        for extent, available in zip(window_size_logical, work_area_size_px)
        if extent > 0 and extent * device_scale > available
    ]

    if not missing:
        return 1.0

    return max(MIN_SCALE_FACTOR, math.floor(min(missing) * 100) / 100)


def work_area_metrics():
    """
    Read the work area size and the system DPI from Windows.

    Both readings come from the same DPI context, so they stay consistent
    whether or not the process is DPI aware: an unaware process is handed a
    virtualized work area and a DPI of 96, and the ratio between them is the
    same one an aware process computes from physical pixels.

    Returns:
        tuple or None: (work area width, work area height, system DPI), or None
        when the platform does not offer them.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        rect = wintypes.RECT()

        if not user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return None

        return rect.right - rect.left, rect.bottom - rect.top, float(user32.GetDpiForSystem())
    except Exception as error:
        logging.debug("Could not read the screen metrics: %s", error)
        return None


def configure_scaling():
    """
    Scale the interface down when the window would not fit the screen.

    Qt reads QT_SCALE_FACTOR while the application object is built, so this has
    to run before it. A factor the user set themselves is left alone.
    """
    if os.environ.get('QT_SCALE_FACTOR'):
        return

    metrics = work_area_metrics()
    if metrics is None:
        return

    work_area_width, work_area_height, dpi = metrics
    # The title bar is drawn outside the client area the layout is sized for,
    # and it is the frame that has to fit between the screen edges.
    factor = scale_factor_for(
        (WINDOW_WIDTH_LOGICAL, WINDOW_HEIGHT_LOGICAL + WINDOW_FRAME_HEIGHT_LOGICAL),
        (work_area_width, work_area_height),
        dpi,
    )

    if factor >= 1.0:
        return

    os.environ['QT_SCALE_FACTOR'] = str(factor)
    logging.info(
        "Scaling the interface by %s so the window fits a %sx%s px work area",
        factor, work_area_width, work_area_height,
    )


def fit_to_screen(window):
    """
    Move the window until its frame lies inside the screen work area.

    A window taller than the work area is pinned to its top left corner: the
    bottom is unreachable either way, and a title bar the user can grab is
    worth more than the last row of the window.

    Args:
        window (QWidget): The window to move.
    """
    screen = window.screen() or QApplication.primaryScreen()
    if screen is None:
        return

    available = screen.availableGeometry()
    frame = window.frameGeometry()
    x = max(available.left(), min(frame.left(), available.right() - frame.width() + 1))
    y = max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1))

    window.move(x, y)


def clear_initial_focus(window):
    """
    Start with no settings field highlighted.

    Qt hands the keyboard to the first field that accepts focus, which put the
    caret in a recognizer threshold; a stray arrow key or scroll then changed a
    setting the user never meant to touch.

    Args:
        window (QWidget): The window to take the focus.
    """
    focused = QApplication.focusWidget()
    if focused is not None:
        focused.clearFocus()

    window.setFocus()


def shutdown(exit_code):
    """
    Leave the process, skipping finalizers when a capture worker is stuck.

    A capture worker that never returned from the camera driver is deliberately
    leaked, and so is the camera handle it uses. Normal interpreter shutdown
    would tear that thread object down while it is still running and abort the
    process with 0xC0000409, so the process exits right here instead.

    Args:
        exit_code (int): The exit code reported by the Qt event loop.
    """
    if not stranded_worker_running():
        sys.exit(exit_code)

    logging.error(
        "A camera capture worker is still blocked in the camera driver: leaking the camera "
        "handle and exiting without running finalizers"
    )
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


def main():
    """
    Main function to start the application.
    """
    app_directory = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    os.chdir(app_directory)

    logging.basicConfig(encoding='utf-8', level=logging.INFO)
    configure_scaling()

    app = QApplication(sys.argv)
    if app:
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside6', palette=DarkPalette))
        window = MainApp()
        window.start()
        window.show()
        fit_to_screen(window)
        clear_initial_focus(window)
        logging.info("Sign language translator application has started!")
    shutdown(app.exec())


if __name__ == '__main__':
    main()
