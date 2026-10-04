"""
Hinh hoc trang in KDP cho khổ 8.5 x 11 inch.

Quy uoc toa do: don vi point (1 in = 72 pt), goc tren-trai, truc y huong xuong.

Quy tac KDP (trang ruot sach):
  - Khong bleed: kich thuoc trang = kho cat (8.5 x 11 in), le ngoai/tren/duoi >= 0.25 in.
  - Co bleed:   kich thuoc trang = 8.625 x 11.25 in (them 0.125 in o canh ngoai, tren va duoi;
                canh gay sach khong co bleed), le ngoai/tren/duoi >= 0.375 in tinh tu mep cat.
  - Le trong (gutter) tang theo so trang.
Hay kiem tra lai voi trang tro giup KDP truoc khi xuat ban vi quy dinh co the thay doi.
"""
from dataclasses import dataclass, asdict

PT = 72.0
TRIM_W_IN, TRIM_H_IN = 8.5, 11.0
BLEED_IN = 0.125

GUTTER_TABLE = [  # (so trang toi da, gutter toi thieu in)
    (150, 0.375),
    (300, 0.5),
    (500, 0.625),
    (700, 0.75),
    (828, 0.875),
]


def min_gutter_in(page_count: int) -> float:
    for max_pages, g in GUTTER_TABLE:
        if page_count <= max_pages:
            return g
    return GUTTER_TABLE[-1][1]


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self):
        return self.x + self.w

    @property
    def y2(self):
        return self.y + self.h


@dataclass
class PageGeometry:
    page_w: float
    page_h: float
    trim: Box        # vung sau khi cat
    safe: Box        # vung an toan theo le toi thieu cua KDP
    content: Box     # vung dat tranh = safe thu vao them padding
    bleed: bool
    side: str        # "right" (trang le, recto) | "left" (trang chan, verso)
    gutter_in: float
    outside_in: float

    def info(self):
        d = asdict(self)
        d["page_size_in"] = [round(self.page_w / PT, 3), round(self.page_h / PT, 3)]
        return d


def page_geometry(bleed: bool = True, side: str = "right", page_count: int = 24,
                  padding_in: float = 0.25, extra_margin_in: float = 0.0) -> PageGeometry:
    trim_w, trim_h = TRIM_W_IN * PT, TRIM_H_IN * PT
    b = BLEED_IN * PT if bleed else 0.0
    page_w, page_h = trim_w + b, trim_h + 2 * b

    # trang phai: gay sach o ben trai -> bleed ben phai; trang trai nguoc lai
    trim_x = 0.0 if side == "right" else b
    trim = Box(trim_x, b, trim_w, trim_h)

    gutter = min_gutter_in(page_count) + extra_margin_in
    outside = (0.375 if bleed else 0.25) + extra_margin_in
    g, o = gutter * PT, outside * PT
    left, right = (g, o) if side == "right" else (o, g)
    safe = Box(trim.x + left, trim.y + o, trim_w - left - right, trim_h - 2 * o)

    p = padding_in * PT
    content = Box(safe.x + p, safe.y + p, safe.w - 2 * p, safe.h - 2 * p)
    return PageGeometry(page_w, page_h, trim, safe, content, bleed, side, gutter, outside)
