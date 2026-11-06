"""Strip fonts. (Layout and sizing tests live in test_booth.py.)"""
import os

import pytest

import strip


def test_footer_font_is_bold():
    # On a Mac the old code took face 0 of Helvetica.ttc, which is Regular, not Bold.
    if not any(os.path.exists(p) for p in strip.FONT_CANDIDATES):
        pytest.skip("none of the strip fonts are installed on this machine")
    name, style = strip.load_font(60).getname()
    assert "Bold" in style and "Oblique" not in style, (name, style)


def test_bold_face_found_inside_a_font_collection(monkeypatch):
    # Simulate a .ttc whose faces are in the order Regular, Bold Oblique, Bold.
    faces = [("Sans", "Regular"), ("Sans", "Bold Oblique"), ("Sans", "Bold")]

    class Face:
        def __init__(self, index):
            self.index = index

        def getname(self):
            return faces[self.index]

    def truetype(path, size, index=0):
        if index >= len(faces):
            raise OSError("no such face")
        return Face(index)

    monkeypatch.setattr(strip.ImageFont, "truetype", truetype)
    assert strip._truetype_bold("x.ttc", 40).getname() == ("Sans", "Bold")


def test_font_file_without_bold_falls_back_to_first_face(monkeypatch):
    class Face:
        def getname(self):
            return ("Sans", "Regular")

    def truetype(path, size, index=0):
        if index > 0:
            raise OSError("single-face file")
        return Face()

    monkeypatch.setattr(strip.ImageFont, "truetype", truetype)
    assert strip._truetype_bold("x.ttf", 40).getname() == ("Sans", "Regular")
