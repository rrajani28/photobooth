"""Printing backends. Pick one in config.json -> printer.backend

  none    -> just save the file
  preview -> NO PRINTER NEEDED: saves print.pdf at true physical size (4x6 in) and pops it open
             on screen like a print sliding out. The PDF/PNG can be printed later at any
             drugstore photo kiosk or library printer.
  system  -> send to a normal printer through the OS
             Mac/Linux/Pi: CUPS `lp` command   |   Windows: default print handler
             Use this for photo printers like a Canon Selphy.
  escpos  -> USB thermal receipt printer (58mm/80mm), talked to directly, no drivers.
             Needs: pip install python-escpos
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps


class PrintError(Exception):
    pass


def thermal_prepare(img, width_px=384):
    """Scale to the printer's dot width and dither to pure black/white.
    58mm printers are usually 384 dots wide, 80mm printers 576."""
    img = img.convert("L")
    h = round(img.height * width_px / img.width)
    img = img.resize((width_px, h), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)   # thermal prints wash out; boost contrast
    return img.convert("1")                       # Floyd-Steinberg dithering


def open_file(path):
    """Open a file in the OS default app. Returns False if there's no way to (e.g. a server).
    On a Mac it opens in the background (`open -g`): the viewer shows the file but the booth keeps
    the keyboard, so the next SPACE still starts a session instead of going to Preview."""
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa
        return True
    cmd = ["open", "-g"] if sys.platform == "darwin" else ["xdg-open"]
    if shutil.which(cmd[0]) is None:
        return False
    subprocess.Popen(cmd + [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def _print_preview(path, cfg):
    path = Path(path)
    img = Image.open(path)
    dpi = round(img.info.get("dpi", (300, 300))[0])
    pdf_path = path.with_suffix(".pdf")
    img.convert("RGB").save(pdf_path, resolution=dpi)   # resolution = true size in the PDF
    w_in, h_in = img.width / dpi, img.height / dpi
    opened = cfg.get("open_preview", True) and open_file(pdf_path)
    return (f"Preview {'opened' if opened else 'saved'}: {pdf_path.name} "
            f"({w_in:g}x{h_in:g} in)")


def _print_system(path, cfg):
    copies = int(cfg.get("copies", 1))
    if sys.platform.startswith("win"):
        for _ in range(copies):
            os.startfile(str(path), "print")      # noqa: uses the default app's print verb
        return f"Sent to default Windows printer ({copies}x)"

    if shutil.which("lp") is None:
        raise PrintError("`lp` not found. On a Pi: sudo apt install cups")
    cmd = ["lp", "-n", str(copies)]
    if cfg.get("printer_name"):
        cmd += ["-d", cfg["printer_name"]]
    for opt in cfg.get("lp_options", []):
        cmd += ["-o", opt]
    cmd.append(str(path))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise PrintError(f"lp failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip() or "Sent to printer"


def _print_escpos(path, cfg):
    try:
        from escpos.printer import Usb
    except ImportError as e:
        raise PrintError("Install python-escpos: pip install python-escpos") from e
    vid = int(str(cfg["escpos_vendor_id"]), 16)
    pid = int(str(cfg["escpos_product_id"]), 16)
    img = thermal_prepare(Image.open(path), int(cfg.get("thermal_width_px", 384)))
    try:
        p = Usb(vid, pid)
    except Exception as e:  # noqa: escpos raises several USB error types
        raise PrintError(f"Thermal printer {hex(vid)}:{hex(pid)} not found ({e}). "
                         "Run `lsusb` on the Pi to get the right IDs.") from e
    try:
        for _ in range(int(cfg.get("copies", 1))):
            p.image(img)
            p.text("\n\n\n")
            try:
                p.cut()
            except Exception:
                pass  # many cheap printers have no cutter; tear it off
    finally:
        p.close()   # always let go of the USB port, or every later print fails with "busy"
    return "Printed on thermal printer"


def print_image(path, cfg):
    backend = cfg.get("backend", "none")
    if backend == "none":
        return "Saved (printing is off)"
    if backend == "preview":
        return _print_preview(path, cfg)
    if backend == "system":
        return _print_system(path, cfg)
    if backend == "escpos":
        return _print_escpos(path, cfg)
    raise PrintError(f"Unknown printer backend '{backend}'")
