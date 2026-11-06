"""Camera access.

Camera      -> any USB/built-in webcam via OpenCV (works on Mac, Windows, Linux, Raspberry Pi)
FakeCamera  -> generates fake frames so you can test everything without a webcam
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def _backend():
    """Pick the fastest OpenCV capture backend for this OS."""
    if sys.platform.startswith("win"):
        return cv2.CAP_DSHOW          # opens much faster than the default on Windows
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_V4L2               # Linux / Raspberry Pi


class Camera:
    def __init__(self, index=0, width=1920, height=1080):
        self.index = index
        self.cap = cv2.VideoCapture(index, _backend())
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Couldn't open camera {index}. Run `python booth.py --list-cameras` to find "
                "the right index. On a Mac, also allow Terminal camera access in "
                "System Settings > Privacy & Security > Camera."
            )
        # MJPG lets cheap USB webcams hit 1080p at a usable frame rate (raw YUYV crawls at ~5 fps).
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # Let auto-exposure / white balance settle so the first photo isn't dark.
        for _ in range(15):
            self.cap.read()

        frame = self.read()
        self.resolution = (frame.shape[1], frame.shape[0])
        print(f"[camera] index {index} running at {self.resolution[0]}x{self.resolution[1]}")
        if frame.mean() < 15:
            print(f"[camera] WARNING: camera {index} is sending an all-black image. Wrong camera "
                  "(e.g. a phone in your pocket), lens covered, or another app is using it? "
                  "Run `python booth.py --list-cameras` to see a snapshot from each camera.")

    def read(self):
        """Return the newest frame as a BGR numpy array."""
        ok, frame = self.cap.read()
        if not ok or frame is None:
            raise RuntimeError("Camera stopped returning frames (unplugged?).")
        return frame

    def release(self):
        self.cap.release()


class FakeCamera:
    """Stand-in camera: moving shapes + a frame counter. Same interface as Camera."""

    def __init__(self, width=1280, height=720, **_):
        self.resolution = (width, height)
        self.n = 0
        self.t0 = time.time()
        print(f"[camera] FAKE camera at {width}x{height}")

    def read(self):
        w, h = self.resolution
        self.n += 1
        t = time.time() - self.t0
        x = np.linspace(0, 255, w, dtype=np.float32)
        y = np.linspace(0, 255, h, dtype=np.float32)[:, None]
        frame = np.zeros((h, w, 3), np.uint8)
        frame[..., 0] = (x * 0.6 + 60 * np.sin(t)).clip(0, 255)        # B
        frame[..., 1] = (y * 0.5 + 40).clip(0, 255)                    # G
        frame[..., 2] = (255 - x * 0.5).clip(0, 255)                   # R
        cx = int(w / 2 + w * 0.25 * np.sin(t * 1.3))
        cv2.circle(frame, (cx, h // 2), h // 5, (235, 225, 215), -1)   # "face"
        cv2.circle(frame, (cx - h // 14, h // 2 - h // 20), h // 40, (40, 40, 40), -1)
        cv2.circle(frame, (cx + h // 14, h // 2 - h // 20), h // 40, (40, 40, 40), -1)
        cv2.ellipse(frame, (cx, h // 2 + h // 20), (h // 12, h // 24), 0, 0, 180, (40, 40, 40), 4)
        cv2.putText(frame, f"FAKE CAM  #{self.n}", (int(w * 0.2), int(h * 0.12)), cv2.FONT_HERSHEY_SIMPLEX,
                    1.4, (255, 255, 255), 3, cv2.LINE_AA)
        return frame

    def release(self):
        pass


def _linux_camera_name(index):
    """On Linux/Pi, V4L2 index N is /dev/videoN and the kernel knows its name. Elsewhere: None."""
    try:
        with open(f"/sys/class/video4linux/video{index}/name") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _set_opencv_log_level(level):
    """Quiet OpenCV's [WARN] lines while probing indexes that don't exist. Returns the old level
    (or None on builds without cv2.utils.logging, where this does nothing)."""
    logging = getattr(getattr(cv2, "utils", None), "logging", None)
    if logging is None:
        return None
    old = logging.getLogLevel()
    logging.setLogLevel(level)
    return old


def _probe(index, settle_seconds=1.0):
    """Open one camera index. Returns the last good frame after letting exposure settle, or None.
    Reads several frames because the first read right after opening can fail (common on macOS),
    and the first good frames can be black while auto-exposure starts up."""
    cap = cv2.VideoCapture(index, _backend())
    try:
        if not cap.isOpened():
            return None
        frame = None
        end = time.time() + settle_seconds
        while time.time() < end:
            ok, f = cap.read()
            if ok and f is not None:
                frame = f
        return frame
    finally:
        cap.release()


def list_cameras(max_index=6, snapshot_dir=None):
    """Print which camera indexes work. If snapshot_dir is given, save one photo per camera there,
    so you can SEE which index is which (a Mac with an iPhone nearby has two cameras, and the
    index order isn't something you can guess)."""
    # flush so this prints before OpenCV's own messages about missing indexes, not after them
    print(f"Checking camera indexes 0-{max_index - 1} (errors about missing indexes are normal)...",
          flush=True)
    old_level = _set_opencv_log_level(2)          # 2 = errors only
    try:
        found = []
        for i in range(max_index):
            frame = _probe(i)
            if frame is not None:
                found.append((i, frame))
    finally:
        if old_level is not None:
            _set_opencv_log_level(old_level)

    if not found:
        print("No cameras found.")
        if sys.platform == "darwin":
            print("On a Mac this is almost always permission. Open System Settings > Privacy & Security > "
                  "Camera and switch on the app you ran this from (Terminal, iTerm, VS Code...). "
                  "Then run this again.")
        else:
            print("Check the camera is plugged in and not in use by another app (Zoom, Teams, a browser tab).")
        return []

    if snapshot_dir is not None:
        snapshot_dir = Path(snapshot_dir)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for i, frame in found:
        h, w = frame.shape[:2]
        line = f"  camera {i}: {w}x{h} (default resolution)"
        name = _linux_camera_name(i)
        if name:
            line += f"  [{name}]"
        if frame.mean() < 15:
            line += "  (image is black: lens covered, or another app is using it?)"
        if snapshot_dir is not None:
            path = snapshot_dir / f"camera_{i}.jpg"
            cv2.imwrite(str(path), frame)
            line += f"\n      snapshot: {path}"
        print(line)
        results.append((i, w, h))
    if snapshot_dir is not None:
        print("Open the snapshots to see which camera is which, then use that index with --camera.")
    return results
