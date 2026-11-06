#!/usr/bin/env python3
"""Photobooth: live preview -> countdown -> N photos -> strip -> print.

  python booth.py                 run the booth (SPACE = start, F = fullscreen, Q/ESC = quit)
  python booth.py --list-cameras  find your webcam's index (saves a snapshot from each camera)
  python booth.py --camera 1      use camera 1 instead of the one in config.json
  python booth.py --fake-camera   test without a webcam
  python booth.py --headless      one session, no window (for testing over SSH on the Pi)
"""
import argparse
import copy
import datetime
import json
import math
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from camera import FakeCamera, list_cameras, open_camera
from printer import PrintError, print_image
from strip import compose_sheet, compose_strip, frame_to_pil
from trigger import Trigger

HERE = Path(__file__).resolve().parent
WINDOW = "Photobooth"

DEFAULTS = {
    "camera": {"index": 0, "width": 1920, "height": 1080},
    "shots": 4,
    "countdown_seconds": 3,
    "pause_between_shots": 1.0,
    "review_seconds": 6,
    "mirror_preview": True,
    "mirror_saved": False,
    "fullscreen": False,
    "strip": {
        "layout": "4x6_double",
        "dpi": 300,
        "footer_text": "PHOTOBOOTH",
        "show_date": True,
        "date_format": "%b %d, %Y",
        "background": "#FFFFFF",
        "text_color": "#111111",
        "grayscale": False,
    },
    "printer": {
        "backend": "preview",
        "open_preview": True,
        "printer_name": "",
        "copies": 1,
        "lp_options": ["fit-to-page"],
        "escpos_vendor_id": "0x0416",
        "escpos_product_id": "0x5011",
        "thermal_width_px": 384,
    },
    "trigger": {"gpio_pin": None},
    "output_dir": "output",
}


# ---------- config ----------
def deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path):
    path = Path(path)
    if path.exists():
        with open(path) as f:
            return deep_merge(DEFAULTS, json.load(f))
    print(f"[config] {path} not found, using defaults")
    return copy.deepcopy(DEFAULTS)


# ---------- saving / composing (no UI, so it's testable and reused by headless mode) ----------
def output_root(cfg):
    """output_dir from config; relative paths are relative to this folder, not wherever you ran it from."""
    out_root = Path(cfg["output_dir"])
    return out_root if out_root.is_absolute() else HERE / out_root


def build_session(shots_bgr, cfg, now=None):
    """Save raw shots + strip + print sheet. Returns (session_dir, sheet_path, sheet_image)."""
    now = now or datetime.datetime.now()
    session_dir = output_root(cfg) / now.strftime("%Y%m%d_%H%M%S")
    session_dir.mkdir(parents=True, exist_ok=True)

    photos = []
    for i, frame in enumerate(shots_bgr, 1):
        if cfg["mirror_saved"]:
            frame = cv2.flip(frame, 1)
        cv2.imwrite(str(session_dir / f"shot_{i}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        photos.append(frame_to_pil(frame))

    s = cfg["strip"]
    strip = compose_strip(
        photos,
        footer_text=s["footer_text"],
        date_text=now.strftime(s["date_format"]) if s["show_date"] else "",
        dpi=s["dpi"],
        background=s["background"],
        text_color=s["text_color"],
        grayscale=s["grayscale"],
    )
    strip.save(session_dir / "strip.png", dpi=(s["dpi"], s["dpi"]))
    sheet = compose_sheet(strip, s["layout"], s["dpi"])
    sheet_path = session_dir / "print.png"
    sheet.save(sheet_path, dpi=(s["dpi"], s["dpi"]))
    return session_dir, sheet_path, sheet


def do_print(sheet_path, cfg):
    """Never raises: a failed print shows up as a message, and the booth keeps running.
    Printer libraries raise their own errors (USB unplugged, out of paper...), not just PrintError."""
    try:
        return print_image(sheet_path, cfg["printer"])
    except PrintError as e:
        return f"PRINT FAILED: {e}"
    except Exception as e:  # noqa: BLE001
        return f"PRINT FAILED: {type(e).__name__}: {e}"


# ---------- drawing helpers ----------
def draw_center_text(img, text, rel_height, y_rel=0.5, color=(255, 255, 255)):
    """Big outlined text that stays readable on any background. rel_height = text height / image height."""
    h, w = img.shape[:2]
    font = cv2.FONT_HERSHEY_DUPLEX
    (tw, th), _ = cv2.getTextSize(text, font, 1.0, 2)
    scale = (h * rel_height) / th
    scale = min(scale, (w * 0.9) / tw)           # never wider than 90% of the frame
    thick = max(2, int(scale * 2))
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    x, y = int((w - tw) / 2), int(h * y_rel + th / 2)
    # Outline: stamp the text in black around the edges first (works on every OpenCV version).
    r = max(2, round(th * 0.06))
    for dx in (-r, 0, r):
        for dy in (-r, 0, r):
            if dx or dy:
                cv2.putText(img, text, (x + dx, y + dy), font, scale, (0, 0, 0), thick, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), font, scale, color, thick, cv2.LINE_AA)
    return img


def fit_to_canvas(img, canvas_w, canvas_h, bg=(20, 20, 20)):
    """Letterbox an image onto a fixed-size canvas (used to show the strip on screen)."""
    h, w = img.shape[:2]
    s = min(canvas_w / w, canvas_h / h)
    resized = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    canvas = np.full((canvas_h, canvas_w, 3), bg, np.uint8)
    y, x = (canvas_h - resized.shape[0]) // 2, (canvas_w - resized.shape[1]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas


# ---------- the interactive booth ----------
class Booth:
    def __init__(self, cfg, camera):
        self.cfg = cfg
        self.cam = camera
        self.trigger = Trigger(cfg["trigger"].get("gpio_pin"))
        self.fullscreen = cfg["fullscreen"]
        self.quit = False
        self._visible_works = False   # becomes True once the window reports itself visible

    # window plumbing
    def _setup_window(self):
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        w, h = self.cam.resolution
        scale = min(1280 / w, 720 / h, 1.0)
        cv2.resizeWindow(WINDOW, int(w * scale), int(h * scale))
        self._apply_fullscreen()

    def _apply_fullscreen(self):
        mode = cv2.WINDOW_FULLSCREEN if self.fullscreen else cv2.WINDOW_NORMAL
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, mode)

    def _show(self, img):
        cv2.imshow(WINDOW, img)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q"), ord("Q")):
            self.quit = True
        elif key in (ord("f"), ord("F")):
            self.fullscreen = not self.fullscreen
            self._apply_fullscreen()
        # Closing the window with the X button also quits.
        if self._window_closed():
            self.quit = True
        return key

    def _window_closed(self):
        """True once the window's X button was clicked. OpenCV builds disagree on how to say that:
        most report VISIBLE = 0, macOS raises an error because the window is gone, and some older
        builds (e.g. the Pi's system OpenCV) don't support VISIBLE at all and always answer -1.
        So a "not visible" answer only counts after the window has reported itself visible once;
        on builds that never do, Q/ESC still quits."""
        try:
            visible = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE)
        except cv2.error:
            return True
        if visible >= 1:
            self._visible_works = True
            return False
        return self._visible_works

    def _live(self):
        """Returns (raw frame for saving, display frame for the screen)."""
        raw = self.cam.read()
        disp = cv2.flip(raw, 1) if self.cfg["mirror_preview"] else raw.copy()
        return raw, disp

    # main loop
    def run(self):
        self._setup_window()
        try:
            while not self.quit:
                _, disp = self._live()
                draw_center_text(disp, "Press SPACE to start", 0.07, 0.88)
                key = self._show(disp)
                if self.trigger.fired(key):
                    self.session()
        finally:
            self.cam.release()
            cv2.destroyAllWindows()

    def session(self):
        n = self.cfg["shots"]
        shots = []
        for i in range(1, n + 1):
            # countdown with live preview
            end = time.time() + self.cfg["countdown_seconds"]
            while (remaining := end - time.time()) > 0:
                _, disp = self._live()
                draw_center_text(disp, str(math.ceil(remaining)), 0.35, 0.5)
                draw_center_text(disp, f"Photo {i} of {n}", 0.06, 0.1)
                self._show(disp)
                if self.quit:
                    return

            raw = self.cam.read()           # the actual photo, full resolution
            shots.append(raw)

            # white flash
            flash = np.full_like(raw, 255)
            t = time.time()
            while time.time() - t < 0.15:
                self._show(flash)

            # hold the photo on screen briefly so people see what was taken
            frozen = cv2.flip(raw, 1) if self.cfg["mirror_preview"] else raw.copy()
            t = time.time()
            while time.time() - t < self.cfg["pause_between_shots"]:
                self._show(frozen)
                if self.quit:
                    return

        self.trigger.clear()
        self._finish(shots)

    def _finish(self, shots):
        w, h = self.cam.resolution
        working = draw_center_text(np.full((h, w, 3), 20, np.uint8), "Making your strip...", 0.07)
        self._show(working)

        session_dir, sheet_path, sheet = build_session(shots, self.cfg)
        print(f"[booth] saved {session_dir}")

        status = {"msg": "Printing..." if self.cfg["printer"]["backend"] != "none" else "Saved!"}

        def worker():
            status["msg"] = do_print(sheet_path, self.cfg)
            print(f"[printer] {status['msg']}")

        threading.Thread(target=worker, daemon=True).start()

        sheet_bgr = np.array(sheet)[:, :, ::-1]
        t = time.time()
        while time.time() - t < self.cfg["review_seconds"] and not self.quit:
            # strip in the top 86% of the screen, status text in its own band below (no overlap)
            band = int(h * 0.14)
            view = np.full((h, w, 3), 20, np.uint8)
            view[: h - band] = fit_to_canvas(sheet_bgr, w, h - band)
            sub = view[h - band:]
            draw_center_text(sub, status["msg"][:60], 0.40, 0.5)
            key = self._show(view)
            if key == 32:          # SPACE skips the review screen
                break
        self.trigger.clear()


def run_headless(cfg, camera):
    """One session, console only. Good for checking camera + printer over SSH."""
    n = cfg["shots"]
    shots = []
    for i in range(1, n + 1):
        # Same countdown as the window version, so a decimal countdown_seconds (2.5) works here too.
        end = time.time() + cfg["countdown_seconds"]
        shown = None
        while (remaining := end - time.time()) > 0:
            if math.ceil(remaining) != shown:
                shown = math.ceil(remaining)
                print(f"  photo {i}/{n} in {shown}...")
            camera.read()            # keep the buffer fresh so the photo isn't stale
        shots.append(camera.read())
        print(f"  snap {i}")
    camera.release()
    session_dir, sheet_path, _ = build_session(shots, cfg)
    print(f"[booth] saved {session_dir}")
    print(f"[printer] {do_print(sheet_path, cfg)}")
    return session_dir


def main():
    ap = argparse.ArgumentParser(description="Webcam photobooth")
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--camera", type=int, help="camera index (overrides config)")
    ap.add_argument("--fake-camera", action="store_true", help="no webcam needed")
    ap.add_argument("--headless", action="store_true", help="one session, no window")
    ap.add_argument("--list-cameras", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.list_cameras:
        list_cameras(snapshot_dir=output_root(cfg) / "cameras")
        return

    if args.camera is not None:
        cfg["camera"]["index"] = args.camera

    cam_cfg = cfg["camera"]
    # The config's camera may have changed number since it was set (devices come and go), so fall
    # back to another working camera. An index typed with --camera means exactly that camera.
    camera = (FakeCamera() if args.fake_camera
              else open_camera(cam_cfg["index"], cam_cfg["width"], cam_cfg["height"],
                               fallback=args.camera is None))

    if args.headless:
        run_headless(cfg, camera)
    else:
        Booth(cfg, camera).run()


if __name__ == "__main__":
    main()
