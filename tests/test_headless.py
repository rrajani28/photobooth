"""Headless mode (one session, no window), with a fake camera (no webcam needed)."""
import booth
from camera import FakeCamera


def test_headless_accepts_decimal_countdown(tmp_path, capsys):
    # range(2.5, 0, -1) used to crash here, while the window version handled 2.5 fine.
    cfg = booth.deep_merge(booth.DEFAULTS, {
        "shots": 2, "countdown_seconds": 0.3, "output_dir": str(tmp_path),
        "printer": {"backend": "none"},
    })
    session_dir = booth.run_headless(cfg, FakeCamera())
    assert (session_dir / "shot_2.jpg").exists() and (session_dir / "print.png").exists()
    out = capsys.readouterr().out
    assert "photo 1/2 in 1..." in out and "snap 2" in out


def test_headless_countdown_prints_each_second_once(tmp_path, capsys):
    cfg = booth.deep_merge(booth.DEFAULTS, {
        "shots": 1, "countdown_seconds": 2, "output_dir": str(tmp_path),
        "printer": {"backend": "none"},
    })
    booth.run_headless(cfg, FakeCamera())
    lines = [line.strip() for line in capsys.readouterr().out.splitlines() if "photo 1/1 in" in line]
    assert lines == ["photo 1/1 in 2...", "photo 1/1 in 1..."]
