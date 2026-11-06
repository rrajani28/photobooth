"""Camera selection: --list-cameras, and falling back when the configured camera is missing
or black. Cameras are faked out (no webcam needed)."""
import sys

import cv2
import numpy as np
import pytest

import booth
import camera


def bright(w=640, h=480):
    return np.full((h, w, 3), 120, np.uint8)


def black(w=640, h=480):
    return np.zeros((h, w, 3), np.uint8)


def fake_probe(frames_by_index):
    return lambda index, settle_seconds=1.0: frames_by_index.get(index)


def test_list_cameras_saves_a_snapshot_per_camera(monkeypatch, tmp_path, capsys):
    # A Mac with an iPhone nearby has two cameras; the index alone can't tell you which is which.
    monkeypatch.setattr(camera, "_probe", fake_probe({0: black(), 1: bright(1920, 1080)}))
    found = camera.list_cameras(snapshot_dir=tmp_path / "cameras")
    assert found == [(0, 640, 480), (1, 1920, 1080)]
    snap = cv2.imread(str(tmp_path / "cameras" / "camera_1.jpg"))
    assert snap.shape == (1080, 1920, 3) and snap.mean() > 100
    assert (tmp_path / "cameras" / "camera_0.jpg").exists()
    out = capsys.readouterr().out
    assert "camera_1.jpg" in out


def test_list_cameras_flags_black_camera(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(camera, "_probe", fake_probe({0: black(), 1: bright()}))
    camera.list_cameras(snapshot_dir=tmp_path)
    lines = capsys.readouterr().out.splitlines()
    cam0 = next(line for line in lines if "camera 0:" in line)
    cam1 = next(line for line in lines if "camera 1:" in line)
    assert "black" in cam0 and "black" not in cam1


def test_no_cameras_on_mac_points_at_permission_settings(monkeypatch, capsys):
    monkeypatch.setattr(camera, "_probe", fake_probe({}))
    monkeypatch.setattr(camera.sys, "platform", "darwin")
    assert camera.list_cameras() == []
    out = capsys.readouterr().out
    assert "Privacy & Security" in out and "Camera" in out


def test_no_cameras_elsewhere_gives_a_hint(monkeypatch, capsys):
    monkeypatch.setattr(camera, "_probe", fake_probe({}))
    monkeypatch.setattr(camera.sys, "platform", "linux")
    camera.list_cameras()
    assert "plugged in" in capsys.readouterr().out


def test_list_cameras_shows_linux_device_name(monkeypatch, capsys):
    monkeypatch.setattr(camera, "_probe", fake_probe({0: bright()}))
    monkeypatch.setattr(camera, "_linux_camera_name", lambda i: "USB 2.0 Camera" if i == 0 else None)
    camera.list_cameras()
    assert "[USB 2.0 Camera]" in capsys.readouterr().out


class FlakyCapture:
    """First read fails (common on macOS right after opening), then frames arrive."""

    def __init__(self, *a):
        self.reads = 0

    def isOpened(self):
        return True

    def read(self):
        self.reads += 1
        if self.reads == 1:
            return False, None
        return True, np.full((480, 640, 3), self.reads, np.uint8)

    def release(self):
        pass


def test_probe_survives_failed_first_read_and_returns_latest_frame(monkeypatch):
    monkeypatch.setattr(camera.cv2, "VideoCapture", FlakyCapture)
    frame = camera._probe(0, settle_seconds=0.05)
    assert frame is not None
    assert frame[0, 0, 0] > 2          # a later frame, not the first one


def test_output_root_relative_to_project_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert booth.output_root({"output_dir": "output"}) == booth.HERE / "output"
    assert booth.output_root({"output_dir": str(tmp_path)}) == tmp_path


def test_list_cameras_uses_configured_output_dir(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(booth, "list_cameras", lambda snapshot_dir=None: seen.setdefault("dir", snapshot_dir))
    cfg = tmp_path / "config.json"
    cfg.write_text('{"output_dir": "%s"}' % (tmp_path / "out").as_posix())
    monkeypatch.setattr(sys, "argv", ["booth.py", "--list-cameras", "--config", str(cfg)])
    booth.main()
    assert seen["dir"] == tmp_path / "out" / "cameras"


class BlackCapture:
    """A camera that opens fine but only ever sends black (phone in a pocket, lens cap on)."""

    def __init__(self, *a):
        pass

    def isOpened(self):
        return True

    def set(self, *a):
        return True

    def read(self):
        return True, np.zeros((720, 1280, 3), np.uint8)

    def release(self):
        pass


def test_camera_warns_when_image_is_all_black(monkeypatch, capsys):
    monkeypatch.setattr(camera.cv2, "VideoCapture", BlackCapture)
    cam = camera.Camera(0, 1280, 720)
    assert cam.resolution == (1280, 720)
    assert "all-black" in capsys.readouterr().out


def capture_factory(frames_by_index):
    """Fake cv2.VideoCapture where each index is: a frame it keeps sending, or missing (None)."""
    released = []

    class Cap:
        def __init__(self, index, *backend):
            self.index, self.frame = index, frames_by_index.get(index)

        def isOpened(self):
            return self.frame is not None

        def set(self, *a):
            return True

        def read(self):
            return (True, self.frame.copy()) if self.frame is not None else (False, None)

        def release(self):
            released.append(self.index)

    return Cap, released


def test_open_camera_uses_configured_camera_when_it_works(monkeypatch):
    cap, _ = capture_factory({0: bright(), 1: bright()})
    monkeypatch.setattr(camera.cv2, "VideoCapture", cap)
    assert camera.open_camera(1, probe_seconds=0.01).index == 1


def test_open_camera_falls_back_when_configured_camera_is_gone(monkeypatch, capsys):
    # The MacBook camera moved from 1 to 0 after macOS dropped the iPhone from its list.
    cap, _ = capture_factory({0: bright()})
    monkeypatch.setattr(camera.cv2, "VideoCapture", cap)
    cam = camera.open_camera(1, probe_seconds=0.01)
    assert cam.index == 0
    assert "Using camera 0 instead of 1" in capsys.readouterr().out


def test_open_camera_skips_a_black_camera(monkeypatch, capsys):
    # A switched-off iPhone that macOS still lists: it opens, but only sends black.
    cap, released = capture_factory({0: black(), 1: bright()})
    monkeypatch.setattr(camera.cv2, "VideoCapture", cap)
    cam = camera.open_camera(0, probe_seconds=0.01)
    assert cam.index == 1 and not cam.is_black
    assert 0 in released                     # the black camera was let go
    assert "Using camera 1 instead of 0" in capsys.readouterr().out


def test_open_camera_keeps_black_camera_if_nothing_better(monkeypatch):
    # One webcam with its lens cap on: nothing to switch to, so keep it (the warning says why).
    cap, _ = capture_factory({0: black()})
    monkeypatch.setattr(camera.cv2, "VideoCapture", cap)
    cam = camera.open_camera(0, probe_seconds=0.01)
    assert cam.index == 0 and cam.is_black


def test_open_camera_raises_when_no_camera_works(monkeypatch):
    cap, _ = capture_factory({})
    monkeypatch.setattr(camera.cv2, "VideoCapture", cap)
    with pytest.raises(RuntimeError, match="Couldn't open camera 0"):
        camera.open_camera(0, probe_seconds=0.01)


def test_explicit_camera_choice_never_switches(monkeypatch):
    cap, _ = capture_factory({0: black(), 1: bright()})
    monkeypatch.setattr(camera.cv2, "VideoCapture", cap)
    assert camera.open_camera(0, fallback=False, probe_seconds=0.01).index == 0
    with pytest.raises(RuntimeError):
        camera.open_camera(5, fallback=False, probe_seconds=0.01)


def test_camera_releases_device_when_it_never_sends_a_frame(monkeypatch):
    class OpensButSilent:
        released = False

        def __init__(self, *a):
            pass

        def isOpened(self):
            return True

        def set(self, *a):
            return True

        def read(self):
            return False, None

        def release(self):
            OpensButSilent.released = True

    monkeypatch.setattr(camera.cv2, "VideoCapture", OpensButSilent)
    with pytest.raises(RuntimeError):
        camera.Camera(0)
    assert OpensButSilent.released


@pytest.mark.parametrize("argv, expect_fallback", [([], True), (["--camera", "1"], False)])
def test_booth_only_falls_back_for_the_config_camera(monkeypatch, tmp_path, argv, expect_fallback):
    seen = {}

    def fake_open(index, w, h, fallback):
        seen.update(index=index, fallback=fallback)
        raise SystemExit  # stop before the booth window opens

    monkeypatch.setattr(booth, "open_camera", fake_open)
    monkeypatch.setattr(sys, "argv", ["booth.py", *argv])
    with pytest.raises(SystemExit):
        booth.main()
    assert seen["fallback"] is expect_fallback
