"""Camera access.

Camera      -> any USB/built-in webcam via OpenCV (works on Mac, Windows, Linux, Raspberry Pi)
FakeCamera  -> generates fake frames so you can test everything without a webcam
"""
import sys
import time

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


def list_cameras(max_index=6):
    """Print which camera indexes exist. Built-in laptop cam is usually 0, a USB webcam usually 1."""
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, _backend())
        if cap.isOpened():
            ok, frame = cap.read()
            if ok and frame is not None:
                found.append((i, frame.shape[1], frame.shape[0]))
        cap.release()
    if not found:
        print("No cameras found.")
    for i, w, h in found:
        print(f"  camera {i}: {w}x{h} (default resolution)")
    return found
