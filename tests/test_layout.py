"""The window has to work on ordinary monitors, not just a 65" TV.

At the minimum window size (900x600) and at common laptop/desktop sizes, every page must fit
horizontally without a sideways scrollbar. Vertical scrolling is allowed (pages sit in scroll areas).
"""
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()  # never touch the real settings

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

SIZES = [(900, 600), (1280, 720), (1366, 768), (1920, 1080)]


@pytest.fixture(scope="module")
def win():
    from s4bridge.core import Core
    from s4bridge.ui import theme
    from s4bridge.ui.mainwindow import MainWindow
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)
    core = Core(demo=True)
    core.save_settings = lambda: None  # window geometry must not land in anyone's real config
    w = MainWindow(core)
    w.show()
    app.processEvents()
    yield w
    core.stop()


def test_minimum_is_small(win):
    hint = win.minimumSizeHint()
    assert win.minimumWidth() <= 900 and win.minimumHeight() <= 600
    assert hint.width() <= 900 and hint.height() <= 600, (hint.width(), hint.height())


@pytest.mark.parametrize("size", SIZES)
def test_pages_fit_horizontally(win, size):
    app = QApplication.instance()
    win.resize(*size)
    for _ in range(3):
        app.processEvents()
    for i in range(win.stack.count()):
        win.go(i)
        for _ in range(3):
            app.processEvents()
        sa = win.stack.widget(i)
        assert isinstance(sa, QScrollArea)
        bar = sa.horizontalScrollBar()
        assert bar.maximum() == 0, f"page {i} scrolls sideways at {size}: {bar.maximum()}px too wide"


def test_sidebar_folds_when_narrow(win):
    app = QApplication.instance()
    win.resize(900, 600)
    app.processEvents()
    assert win.sidebar.width() <= 80
    win.resize(1600, 900)
    app.processEvents()
    assert win.sidebar.width() >= 200
