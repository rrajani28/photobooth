"""Printer backends and print-error handling, with the OS and USB faked out (no printer needed)."""
import sys
import types

import pytest
from PIL import Image

import booth
import printer


@pytest.fixture
def popen_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(printer.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(printer.shutil, "which", lambda name: "/usr/bin/" + name)
    return calls


def test_mac_preview_opens_in_background_so_booth_keeps_keyboard(monkeypatch, popen_calls):
    # Plain `open` makes Preview the active app, so the next SPACE went to Preview, not the booth.
    monkeypatch.setattr(printer.sys, "platform", "darwin")
    assert printer.open_file("print.pdf") is True
    assert popen_calls == [["open", "-g", "print.pdf"]]


def test_linux_preview_uses_xdg_open(monkeypatch, popen_calls):
    monkeypatch.setattr(printer.sys, "platform", "linux")
    printer.open_file("print.pdf")
    assert popen_calls == [["xdg-open", "print.pdf"]]


def test_no_viewer_available_reports_false(monkeypatch):
    monkeypatch.setattr(printer.sys, "platform", "linux")
    monkeypatch.setattr(printer.shutil, "which", lambda name: None)
    assert printer.open_file("print.pdf") is False


@pytest.mark.parametrize("error", [OSError("USB unplugged"), RuntimeError("out of paper")])
def test_any_printer_error_becomes_a_message_not_a_crash(monkeypatch, tmp_path, error):
    # Only PrintError used to be caught; anything else killed headless mode / the print thread.
    def broken(*a):
        raise error
    monkeypatch.setattr(booth, "print_image", broken)
    msg = booth.do_print(tmp_path / "print.png", booth.DEFAULTS)
    assert msg.startswith("PRINT FAILED") and str(error) in msg


def test_thermal_printer_releases_usb_even_when_printing_fails(monkeypatch, tmp_path):
    state = {"closed": False}

    class FakeUsb:
        def __init__(self, vid, pid):
            pass

        def image(self, img):
            raise OSError("printer jammed")

        def close(self):
            state["closed"] = True

    fake_escpos = types.ModuleType("escpos")
    fake_escpos.printer = types.SimpleNamespace(Usb=FakeUsb)
    monkeypatch.setitem(sys.modules, "escpos", fake_escpos)
    monkeypatch.setitem(sys.modules, "escpos.printer", fake_escpos.printer)

    p = tmp_path / "print.png"
    Image.new("RGB", (600, 1800), "white").save(p)
    cfg = dict(booth.DEFAULTS["printer"], backend="escpos")
    with pytest.raises(OSError):
        printer.print_image(p, cfg)
    assert state["closed"], "USB handle left open: every later print would fail as 'busy'"
