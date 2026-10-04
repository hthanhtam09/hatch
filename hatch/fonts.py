"""
Font nhung vao PDF. KDP yeu cau moi font phai duoc nhung, nen khong dung font chuan Helvetica cua reportlab.
Lato (SIL Open Font License) nam trong hatch/fonts, dung thuong mai duoc.
"""
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FILES = {"regular": "Lato-Regular.ttf", "bold": "Lato-Bold.ttf", "italic": "Lato-Italic.ttf"}
NAMES = {}


def register():
    if NAMES:
        return NAMES
    for style, fname in FILES.items():
        name = "Lato-" + style
        pdfmetrics.registerFont(TTFont(name, os.path.join(DIR, fname)))
        NAMES[style] = name
    return NAMES


def pdf_name(style="regular"):
    return register()[style]


def width(s, size, style="regular"):
    return pdfmetrics.stringWidth(s, pdf_name(style), size)


def wrap(text, size, max_w, style="regular"):
    """Ngat dong theo do rong that cua font. Giu ngat doan bang '\\n'."""
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            cand = (line + " " + word).strip()
            if line and width(cand, size, style) > max_w:
                out.append(line)
                line = word
            else:
                line = cand
        out.append(line)
    return out
