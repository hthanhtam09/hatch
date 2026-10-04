"""
Cac trang khong phai tranh: trang ten sach, ban quyen, huong dan, khoi dong, tieu de dap an.
Noi dung tieng Anh (thi truong KDP), cau chu tu viet, khong lay tu sach mau.
Moi chu va hinh deu nam trong vung an toan (geom.safe).
"""
import random

import numpy as np
from shapely.geometry import Polygon

from . import fonts
from .engine import Design, assign_angles
from .layout import Box, PageGeometry
from .render import StyleParams, draw_design, guide_segments, hatch_segments


def _para(be, text, x, y, w, size=10.5, lead=1.45, gray=0.0, style="regular", anchor="start"):
    """Ve doan van, tra ve y sau dong cuoi."""
    for line in fonts.wrap(text, size, w, style):
        y += size * lead
        tx = x if anchor == "start" else x + w / 2
        be.text(tx, y, line, size, gray, style, anchor)
    return y


def _footer(be, geom, page_no):
    if page_no:
        s = geom.safe
        be.text(s.x + s.w / 2, s.y2 - 4, str(page_no), 8.5, 0.35)


# ----------------------------- trang ten sach -----------------------------
def ornament(box: Box, style: StyleParams, seed=3):
    """Vien da quy nho gom cac tam giac: dung lam hoa van trang ten sach."""
    cx, cy, r = box.w / 2, box.h / 2, min(box.w, box.h) / 2
    ring = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in np.linspace(-np.pi / 2, 1.5 * np.pi, 7)[:-1]]
    inner = [(cx + 0.45 * r * np.cos(a), cy + 0.45 * r * np.sin(a)) for a in np.linspace(-np.pi / 6, 11 * np.pi / 6, 7)[:-1]]
    polys, levels = [], []
    for i in range(6):
        a, b = ring[i], ring[(i + 1) % 6]
        ia, ib = inner[i - 1], inner[i]
        polys += [np.array([a, b, ib]), np.array([a, ib, ia]), np.array([(cx, cy), ia, ib])]
        levels += [(i % 3) + 1, ((i + 1) % 3) + 2, 0 if i % 2 else 5]
    polys = [p.astype(float) for p in polys]
    nbrs = _neighbours(polys)
    angles = assign_angles(polys, levels, nbrs, 30)
    return Design(int(box.w), int(box.h), polys, levels, angles, [np.array(ring)], [], [])


def title_page(be, geom: PageGeometry, proj, style, page_no=None):
    s = geom.safe
    y = s.y + s.h * 0.24
    y = _para(be, proj["title"] or "Untitled", s.x, y, s.w, 34, 1.2, 0, "bold", "middle")
    if proj["subtitle"]:
        y = _para(be, proj["subtitle"], s.x + 30, y + 6, s.w - 60, 15, 1.4, 0.25, "regular", "middle")
    size = 2.1 * 72
    box = Box(s.x + (s.w - size) / 2, y + 50, size, size)
    draw_design(be, ornament(box, style), box, "key", style, guide_scale=0.8)
    if proj["author"]:
        be.text(s.x + s.w / 2, s.y2 - 60, proj["author"], 14, 0.0, "regular")
    if proj["publisher"]:
        be.text(s.x + s.w / 2, s.y2 - 40, proj["publisher"], 10, 0.35, "regular")


def copyright_page(be, geom, proj, style, page_no=None):
    s = geom.safe
    owner = proj["author"] or proj["publisher"] or "the author"
    lines = [
        proj["title"] or "Untitled",
        f"Copyright © {proj['year']} {owner}. All rights reserved.",
        "",
        "No part of this book may be reproduced, stored or shared in any form or by any means, "
        "electronic or mechanical, without written permission from the copyright holder, "
        "except for brief quotations used in reviews.",
        "",
        "You may photocopy pages from this book for your own personal, non-commercial use.",
    ]
    if proj["publisher"]:
        lines += ["", f"Published by {proj['publisher']}"]
    if proj["isbn"]:
        lines += [f"ISBN {proj['isbn']}"]
    lines += [f"First edition {proj['year']}"]
    text = "\n".join(lines)
    n = len(fonts.wrap(text, 9, s.w * 0.62))
    y0 = s.y2 - 40 - n * 9 * 1.5
    _para(be, text, s.x, y0, s.w * 0.62, 9, 1.5, 0.15)
    _footer(be, geom, page_no)


# ----------------------------- trang huong dan -----------------------------
LEGEND = [
    (1, "Light", "Wide, even gaps"),
    (2, "Medium", "Moderate gaps"),
    (3, "Dark", "Lines close together"),
    (4, "Cross-hatch", "One layer, then a second across it"),
    (0, "No mark", "Leave the shape white"),
    (5, "Black", "Already filled for you"),
]


def _sample_shape(x, y, size, k):
    """Da giac mau hoi lech de giong mang trong tranh."""
    j = [(0.08, 0.0), (1.0, 0.12), (0.88, 1.0), (0.0, 0.84)] if k % 2 else [(0.0, 0.1), (0.92, 0.0), (1.0, 0.9), (0.12, 1.0)]
    return np.array([(x + a * size, y + b * size) for a, b in j])


def howto_page(be, geom, proj, style: StyleParams, page_no=None, include_keys=False):
    s = geom.safe
    x, w = s.x + 18, s.w - 36
    y = s.y + 30
    be.text(s.x + s.w / 2, y + 20, "How to Use This Book", 24, 0, "bold")
    y += 34
    y = _para(be, "Every shape in these designs holds a small mark of three gray strokes. The mark tells you "
                  "how to fill that shape with straight, parallel lines. Fill each marked shape from edge to edge "
                  "in the direction and spacing the mark shows. Shapes with no mark stay white.",
              x, y, w, 11, 1.5, 0.1)
    y += 24

    cols, cell_w = 3, w / 3
    shape = 0.82 * 72
    for idx, (lv, name, note) in enumerate(LEGEND):
        cx = x + (idx % cols) * cell_w
        cy = y + (idx // cols) * (shape + 62)
        left = _sample_shape(cx + 6, cy, shape, idx)
        right = _sample_shape(cx + shape + 34, cy, shape, idx)
        for P, done in ((left, False), (right, True)):
            poly = Polygon(P)
            if lv == 5:
                be.fill_poly(P, 0.0)
            elif lv:
                ang = (30, 120, 60, 150, 0, 0)[idx]
                if done:
                    segs = hatch_segments(poly, ang, style.spacing(lv))
                    if lv == 4:
                        segs += hatch_segments(poly, ang + 90, style.spacing(lv))
                    be.lines(segs, style.hatch_w, 0)
                else:
                    be.lines(guide_segments(poly, ang, lv, style), style.guide_w, style.guide_gray)
            be.stroke_poly(P, style.outline_w * 1.4, 0)
        ay = cy + shape / 2
        ax = cx + shape + 12
        be.lines([((ax, ay), (ax + 16, ay)), ((ax + 16, ay), (ax + 11, ay - 4)), ((ax + 16, ay), (ax + 11, ay + 4))], 0.9, 0.3)
        be.text(cx + 6, cy + shape + 17, name, 11, 0, "bold", "start")
        be.text(cx + 6, cy + shape + 31, note, 9, 0.3, "regular", "start")
    y += 2 * (shape + 62) + 10

    be.text(x, y + 14, "Tips", 15, 0, "bold", "start")
    y += 20
    tips = [
        "Match the angle of the mark. Turning the book so your hand moves comfortably helps a lot.",
        "Match the spacing: strokes far apart in the mark mean wide gaps, strokes close together mean tight gaps.",
        "For cross-hatch shapes, finish the first direction completely before you add the second layer.",
        "Fine-liner pens of 0.3, 0.5 and 0.8 mm work well. A thicker pen makes a shape look darker.",
        "Slide a sheet of card behind the page you are working on so ink cannot soak through.",
        "Each design is printed on one side only, so finished pages can be cut out and framed.",
    ]
    if include_keys:
        tips.append("The answer key at the back shows every design fully hatched, if you want to compare.")
    for t in tips:
        be.fill_poly([(x + 2, y + 9), (x + 7, y + 9), (x + 4.5, y + 13.5)], 0.0)
        y = _para(be, t, x + 16, y - 1, w - 16, 10.5, 1.45, 0.1) + 5
    _footer(be, geom, page_no)


# ----------------------------- trang khoi dong -----------------------------
def _neighbours(polys):
    shp = [Polygon(p) for p in polys]
    nb = [set() for _ in polys]
    for i in range(len(shp)):
        for j in range(i + 1, len(shp)):
            if shp[i].intersection(shp[j]).length > 0.5:
                nb[i].add(j)
                nb[j].add(i)
    return nb


def warmup_design(w, h, seed=11):
    rnd = random.Random(seed)
    nx, ny = 5, 6
    gx, gy = w / nx, h / ny
    V = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            jx = 0 if i in (0, nx) else rnd.uniform(-0.22, 0.22) * gx
            jy = 0 if j in (0, ny) else rnd.uniform(-0.22, 0.22) * gy
            V[i, j] = (i * gx + jx, j * gy + jy)
    polys = []
    for i in range(nx):
        for j in range(ny):
            a, b, c, d = V[i, j], V[i + 1, j], V[i + 1, j + 1], V[i, j + 1]
            r = rnd.random()
            if r < 0.35:
                polys += [np.array([a, b, c]), np.array([a, c, d])]
            elif r < 0.6:
                polys += [np.array([a, b, d]), np.array([b, c, d])]
            else:
                polys.append(np.array([a, b, c, d]))
    polys = [p.astype(float) for p in polys]
    pattern = [1, 2, 3, 4, 2, 1, 3, 0, 2, 4, 1, 3, 5, 2, 1, 4, 3, 0]
    levels = [pattern[k % len(pattern)] for k in range(len(polys))]
    rnd.shuffle(levels)
    angles = assign_angles(polys, levels, _neighbours(polys), 30)
    outer = np.array([(0, 0), (w, 0), (w, h), (0, h)], float)
    return Design(int(w), int(h), polys, levels, angles, [outer], [], [])


def warmup_page(be, geom, proj, style, page_no=None):
    s = geom.safe
    pad = geom.content.x - s.x
    be.text(s.x + s.w / 2, s.y + 44, "Warm-Up", 24, 0, "bold")
    y = _para(be, "Practice here before you begin. Aim for straight, parallel lines with even gaps, "
                  "and follow each mark's angle and spacing.", s.x + 40, s.y + 54, s.w - 80, 11, 1.5, 0.1,
              anchor="middle")
    top = y + 22
    box = Box(s.x + pad, top, s.w - 2 * pad, s.y2 - top - pad - 16)
    d = warmup_design(box.w, box.h)
    draw_design(be, d, box, "page", style)
    _footer(be, geom, page_no)


# ----------------------------- trang dap an -----------------------------
def keys_page(be, geom, entries, style, page_no=None, first=False):
    """entries: list cua (design, so thu tu tranh, so trang cua tranh)."""
    s = geom.safe
    pad = geom.content.x - s.x
    top = s.y + pad
    if first:
        be.text(s.x + s.w / 2, s.y + 40, "Answer Key", 22, 0, "bold")
        top = s.y + 64
    n = len(entries)
    cols = 1 if n == 1 else 2
    rows = (n + cols - 1) // cols if n > 1 else 1
    rows = max(rows, 2) if n > 1 else 1
    area = Box(s.x + pad, top, s.w - 2 * pad, s.y2 - top - pad - 16)
    cw, ch = area.w / cols, area.h / rows
    for k, (design, num, pno) in enumerate(entries):
        cx, cy = area.x + (k % cols) * cw, area.y + (k // cols) * ch
        box = Box(cx + 8, cy + 6, cw - 16, ch - 30)
        draw_design(be, design, box, "key", style, guide_scale=1.0 if n == 1 else 0.6)
        cap = f"Design {num}" + (f"  ·  page {pno}" if pno else "")
        be.text(cx + cw / 2, cy + ch - 10, cap, 9, 0.3)
    _footer(be, geom, page_no)
