"""Window behaviour of the interactive booth, with OpenCV's window functions faked out
(no screen needed). Each test pins down a bug found running on a real Mac."""
import cv2
import pytest

import booth
from camera import FakeCamera


class FakeWindow:
    """Stands in for cv2's window functions. `visible` is what WND_PROP_VISIBLE answers next:
    a number, or an exception to raise (what macOS does once the window is destroyed)."""

    def __init__(self, monkeypatch, visible=1.0):
        self.visible = visible
        self.keys = []
        self.fullscreen_calls = []
        monkeypatch.setattr(booth.cv2, "imshow", lambda *a: None)
        monkeypatch.setattr(booth.cv2, "waitKey", lambda *a: self.keys.pop(0) if self.keys else -1)
        monkeypatch.setattr(booth.cv2, "getWindowProperty", self._get)
        monkeypatch.setattr(booth.cv2, "setWindowProperty", lambda *a: self.fullscreen_calls.append(a))

    def _get(self, name, prop):
        if isinstance(self.visible, Exception):
            raise self.visible
        return self.visible


@pytest.fixture
def make_booth():
    return lambda: booth.Booth(booth.DEFAULTS, FakeCamera())


def test_backend_without_visible_support_does_not_quit_instantly(monkeypatch, make_booth):
    # Builds that don't support WND_PROP_VISIBLE always answer -1. The old check (< 1) quit on frame 1.
    win = FakeWindow(monkeypatch, visible=-1.0)
    b = make_booth()
    for _ in range(5):
        b._show(None)
    assert not b.quit


def test_closing_window_on_mac_quits_instead_of_crashing(monkeypatch, make_booth):
    # macOS OpenCV raises cv2.error for a window that no longer exists.
    win = FakeWindow(monkeypatch, visible=1.0)
    b = make_booth()
    b._show(None)
    assert not b.quit
    win.visible = cv2.error("window gone")
    b._show(None)                   # must not raise
    assert b.quit


def test_closing_window_quits_when_backend_reports_zero(monkeypatch, make_booth):
    win = FakeWindow(monkeypatch, visible=1.0)
    b = make_booth()
    b._show(None)
    win.visible = 0.0
    b._show(None)
    assert b.quit


def test_window_not_yet_shown_does_not_count_as_closed(monkeypatch, make_booth):
    # Right after namedWindow some backends say 0 before the first frame is on screen.
    win = FakeWindow(monkeypatch, visible=0.0)
    b = make_booth()
    b._show(None)
    assert not b.quit


@pytest.mark.parametrize("key", ["q", "Q", "\x1b"])
def test_quit_keys_work_with_caps_lock(monkeypatch, make_booth, key):
    win = FakeWindow(monkeypatch)
    win.keys = [ord(key)]
    b = make_booth()
    b._show(None)
    assert b.quit


@pytest.mark.parametrize("key", ["f", "F"])
def test_fullscreen_key_works_with_caps_lock(monkeypatch, make_booth, key):
    win = FakeWindow(monkeypatch)
    win.keys = [ord(key)]
    b = make_booth()
    b._show(None)
    assert b.fullscreen is True
    assert win.fullscreen_calls[-1][2] == cv2.WINDOW_FULLSCREEN
