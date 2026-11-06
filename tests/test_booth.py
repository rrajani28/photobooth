"""Run with:  python -m pytest -q   (no webcam or printer needed)"""
import datetime

import numpy as np
import pytest
from PIL import Image

import booth
from camera import FakeCamera
from printer import print_image, thermal_prepare
from strip import compose_sheet, compose_strip


def photos(n, size=(1920, 1080)):
    return [Image.new("RGB", size, (40 * i, 100, 200)) for i in range(n)]


def test_strip_is_2x6_at_300dpi():
    assert compose_strip(photos(4)).size == (600, 1800)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_strip_any_photo_count(n):
    assert compose_strip(photos(n), date_text="Nov 06, 2026").size == (600, 1800)


def test_mixed_aspect_ratios_dont_break_layout():
    mixed = [Image.new("RGB", s) for s in [(640, 480), (1920, 1080), (1080, 1920), (500, 500)]]
    assert compose_strip(mixed).size == (600, 1800)


def test_photos_fill_slots_no_white_gaps():
    strip = compose_strip([Image.new("RGB", (1280, 720), (255, 0, 0))] * 4)
    arr = np.array(strip)
    # center of each photo slot should be red, not background white
    for y in (150, 520, 900, 1250):
        assert tuple(arr[y, 300]) == (255, 0, 0), y


def test_long_footer_text_shrinks_to_fit():
    compose_strip(photos(4), footer_text="SUPER LONG EVENT NAME THAT WOULD NEVER FIT")


def test_zero_photos_rejected():
    with pytest.raises(ValueError):
        compose_strip([])


def test_double_sheet_is_4x6():
    assert compose_sheet(compose_strip(photos(4)), "4x6_double").size == (1200, 1800)


def test_bad_layout_rejected():
    with pytest.raises(ValueError):
        compose_sheet(compose_strip(photos(1)), "poster")


def test_thermal_prepare_58mm():
    out = thermal_prepare(compose_strip(photos(4)), 384)
    assert out.width == 384 and out.mode == "1" and out.height == 1152


def test_printer_none_backend(tmp_path):
    p = tmp_path / "x.png"
    Image.new("RGB", (10, 10)).save(p)
    assert "Saved" in print_image(p, {"backend": "none"})


def test_config_merge_keeps_defaults():
    merged = booth.deep_merge(booth.DEFAULTS, {"strip": {"footer_text": "HI"}})
    assert merged["strip"]["footer_text"] == "HI"
    assert merged["strip"]["dpi"] == 300          # untouched default survives
    assert booth.DEFAULTS["strip"]["footer_text"] == "PHOTOBOOTH"  # defaults not mutated


def test_full_session_with_fake_camera(tmp_path):
    cfg = booth.deep_merge(booth.DEFAULTS, {"output_dir": str(tmp_path)})
    cam = FakeCamera()
    shots = [cam.read() for _ in range(4)]
    d, sheet_path, sheet = booth.build_session(shots, cfg, now=datetime.datetime(2026, 11, 6, 12, 0))
    assert (d / "shot_1.jpg").exists() and (d / "strip.png").exists() and sheet_path.exists()
    assert sheet.size == (1200, 1800)


def test_preview_backend_makes_true_size_pdf(tmp_path):
    p = tmp_path / "print.png"
    compose_sheet(compose_strip(photos(4)), "4x6_double").save(p, dpi=(300, 300))
    msg = print_image(p, {"backend": "preview", "open_preview": False})
    pdf = (tmp_path / "print.pdf").read_bytes()
    assert "4x6 in" in msg
    assert b"288" in pdf and b"432" in pdf     # 4x6 inches = 288x432 PDF points


def test_preview_strip_layout_is_2x6(tmp_path):
    p = tmp_path / "print.png"
    compose_strip(photos(4)).save(p, dpi=(300, 300))
    assert "2x6 in" in print_image(p, {"backend": "preview", "open_preview": False})
