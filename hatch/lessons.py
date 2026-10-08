"""
Cac trang day tay: Warm-Up 1, Warm-Up 2, Training 1, Training 2.

Muc tieu: nguoi to thay dung cai se gap trong tranh (huong, do day, gach don, gach cheo, mang de trang)
truoc khi to that. Moi ky hieu goi draw_guide / draw_fill trong render.py (bo pattern chung voi tranh that), nen
vach mau o day khop 100% voi vach mau trong sach.
"""
import math
from dataclasses import replace

import numpy as np
from shapely.geometry import LineString, Polygon

from .layout import Box, PageGeometry
from .render import (StyleParams, draw_design, draw_fill, draw_guide, fit_params, fit_transform,
                     hatch_segments, subject_bbox)

# ----------------------------- do dung chung -----------------------------
SHAPES = {
    "tri": [(0.5, 0.0), (1.0, 1.0), (0.0, 1.0)],
    "kite": [(0.0, 0.0), (0.95, 0.38), (0.82, 1.0), (0.12, 0.96)],
    "pent": [(0.5, 0.0), (1.0, 0.38), (0.82, 1.0), (0.18, 1.0), (0.0, 0.38)],
    "hex": [(0.22, 0.0), (0.78, 0.0), (1.0, 0.5), (0.78, 1.0), (0.22, 1.0), (0.0, 0.5)],
    "trap": [(0.2, 0.0), (0.8, 0.0), (1.0, 1.0), (0.0, 1.0)],
    "rhomb": [(0.5, 0.0), (1.0, 0.5), (0.5, 1.0), (0.0, 0.5)],
    "quad": [(0.08, 0.0), (1.0, 0.1), (0.9, 1.0), (0.0, 0.86)],
    "penta2": [(0.3, 0.0), (0.92, 0.18), (1.0, 0.8), (0.4, 1.0), (0.0, 0.5)],
}


def shape(name, box: Box, inset=0.0):
    pts = SHAPES[name]
    return np.array([(box.x + inset + a * (box.w - 2 * inset), box.y + inset + b * (box.h - 2 * inset))
                     for a, b in pts], float)


def _text_center(be, x, y, s, size, gray=0.0, style="regular"):
    be.text(x, y, s, size, gray, style, "middle")


def _wrap_center(be, fonts_wrap, text, cx, y, w, size, lead=1.4, gray=0.15, style="regular"):
    for line in fonts_wrap(text, size, w, style):
        y += size * lead
        be.text(cx, y, line, size, gray, style, "middle")
    return y


def _dash_polyline(be, pts, w=0.8, gray=0.3, dash=3.2, gap=2.6):
    """Net dut doc theo duong gap khuc."""
    segs = []
    on, left = True, dash
    for p, q in zip(pts[:-1], pts[1:]):
        p, q = np.array(p, float), np.array(q, float)
        L = float(np.hypot(*(q - p)))
        if L == 0:
            continue
        d = (q - p) / L
        pos = 0.0
        while pos < L:
            step = min(left, L - pos)
            if on:
                segs.append((tuple(p + d * pos), tuple(p + d * (pos + step))))
            pos += step
            left -= step
            if left <= 1e-9:
                on = not on
                left = dash if on else gap
    be.lines(segs, w, gray)


def trace_arrow(be, x0, y0, x1, y1, bend=0.28):
    """Mui ten net dut cong tu (x0,y0) toi (x1,y1), dau mui dang goc vuong nhu mau."""
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    cx, cy = mx - dy * bend, my + dx * bend
    pts = []
    for i in range(25):
        t = i / 24
        pts.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1,
                    (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1))
    _dash_polyline(be, pts)
    tx, ty = pts[-1][0] - pts[-3][0], pts[-1][1] - pts[-3][1]
    n = math.hypot(tx, ty) or 1
    tx, ty = tx / n, ty / n
    a, b = 6.5, 5.0
    left = (x1 - tx * a - ty * b, y1 - ty * a + tx * b)
    right = (x1 - tx * a + ty * b, y1 - ty * a - tx * b)
    be.lines([((x1, y1), left), ((x1, y1), right)], 1.1, 0.1)


def guides_in(be, poly_pts, ang, lv, style: StyleParams, glen=None, scale=1.0):
    draw_guide(be, Polygon(poly_pts), ang, lv, style, scale, glen)


def fill_in(be, poly_pts, ang, lv, style: StyleParams):
    draw_fill(be, Polygon(poly_pts), ang, lv, style, sample=True)


def outline(be, pts, style, k=1.5):
    be.stroke_poly(pts, style.outline_w * k, 0)


def _title(be, s, wrap, title, sub, intro=None):
    cx = s.x + s.w / 2
    be.text(cx, s.y + 46, title, 32, 0, "bold")
    be.text(cx, s.y + 72, sub, 14.5, 0.05, "bold")
    y = s.y + 72
    if intro:
        y = _wrap_center(be, wrap, intro, cx, y + 4, s.w - 60, 11, 1.45, 0.2, "italic")
    return y


def _rule(be, s, y):
    be.lines([((s.x + 6, y), (s.x2 - 6, y))], 0.6, 0.55)


def _footer(be, geom, page_no):
    if page_no:
        s = geom.safe
        be.text(s.x + s.w / 2, s.y2 - 4, str(page_no), 8.5, 0.35)


def _fonts_wrap():
    from . import fonts
    return fonts.wrap


# ----------------------------- thanh phan giao dien rieng cua cac trang day -----------------------------
def circle_pts(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def badge(be, x, y, n, r=9.0):
    """Huy hieu tron den co so thu tu."""
    be.fill_poly(circle_pts(x, y, r), 0.1)
    be.text(x, y + r * 0.46, str(n), r * 1.28, 1.0, "bold", "middle")


def _tw(text, size, style):
    from . import fonts
    return fonts.width(text, size, style)


def heading(be, s, y, n, text, hint=None):
    badge(be, s.x + 15, y - 4, n)
    be.text(s.x + 31, y, text, 14, 0.05, "bold", "start")
    if hint:
        be.text(s.x + 31 + 16 + _tw(text, 14, "bold") * 1.1, y, hint, 10, 0.4, "italic", "start")


def checkbox(be, x, y, size=9.0):
    be.rect(x, y, size, size, stroke=0.15, width=0.9)


# ----------------------------- Warm-Up 1: huong, khoang cach, to mang -----------------------------
def warmup1_page(be, geom: PageGeometry, proj, style: StyleParams, page_no=None):
    s = geom.safe
    wrap = _fonts_wrap()
    y = _title(be, s, wrap, "Warm-Up 1", "Direction and steady lines.",
               "Three short drills before the real drawings: follow the grey lines, then fill a shape.")
    W = s.w - 12
    x0 = s.x + 6

    # 1. Huong: o chu nhat phu vach mau, 1-2 net da ve san
    y += 26
    heading(be, s, y, 1, "Trace the guide lines", "Go over the dark examples, then add your own.")
    y += 14
    g = 12.0
    tw, th = (W - 3 * g) / 4, 54.0
    for i, (cap, ang) in enumerate((("Rising  /", 135), ("Falling  \\", 45), ("Upright  |", 90), ("Level  \u2014", 0))):
        bx = x0 + i * (tw + g)
        rect = np.array([(bx, y), (bx + tw, y), (bx + tw, y + th), (bx, y + th)], float)
        segs = hatch_segments(Polygon(rect), ang, 8.0)
        be.lines(segs, style.guide_w, style.guide_gray)
        if len(segs) >= 4:
            mid = len(segs) // 2
            pick = [segs[mid - 1], segs[mid + 1]] if ang not in (0, 90) else [segs[mid]]
            be.lines(pick, style.trace_w, style.trace_gray)
        outline(be, rect, style, 1.6)
        be.text(bx + tw / 2, y + th + 13, cap, 9.5, 0.3, "regular", "middle")
    y += th + 36

    # 2. Khoang cach: cung mot mang, 3 muc thua / vua / day
    heading(be, s, y, 2, "Read the spacing", "Wide gaps = light, close gaps = dark.")
    y += 14
    ch = 70.0
    cw = (W - 2 * 20) / 3
    for k, (cap, lv) in enumerate((("Light", 1), ("Medium", 2), ("Dark", 3))):
        bx = x0 + k * (cw + 20)
        pts = shape("pent", Box(bx, y, cw, ch), 2)
        guides_in(be, pts, 135, lv, style, glen=cw * 0.45)
        outline(be, pts, style, 1.6)
        be.text(bx + cw / 2, y + ch + 13, cap, 9.5, 0.3, "regular", "middle")
    y += ch + 36

    # 3. To mang
    heading(be, s, y, 3, "Fill the shape", "Match the angle of the grey mark, edge to edge.")
    y += 14
    gap_y = 14.0
    fh = (s.y2 - 20 - 40 - y - gap_y) / 2
    fw = (W - 2 * 20) / 3
    plan = (("hex", 60, 2), ("tri", 120, 1), ("rhomb", 20, 3),
            ("kite", 100, 1), ("trap", 0, 2), ("pent", 150, 3))
    for k, (nm, ang, lv) in enumerate(plan):
        bx = x0 + (k % 3) * (fw + 20)
        by = y + (k // 3) * (fh + gap_y)
        pts = shape(nm, Box(bx, by, fw, fh), 2)
        guides_in(be, pts, ang, lv, style, glen=min(fw, fh) * 0.5)
        outline(be, pts, style, 1.7)
    be.text(s.x + s.w / 2, s.y2 - 22, "Keep your spacing steady. Focus on direction first.", 11, 0.1, "italic")
    _footer(be, geom, page_no)


# ----------------------------- Warm-Up 2: do day, gach don, gach cheo -----------------------------
def _gem_design(w, h, seed=5):
    """Vien ngoc 8 canh: vong ngoai 8 hinh thang + 8 tam giac o giua."""
    from .engine import Design
    import random
    rnd = random.Random(seed)
    cx, cy = w / 2, h / 2
    ri = (w * 0.24, h * 0.24)
    ang = [math.radians(22.5 + 45 * k) for k in range(8)]
    O = [(cx + w / 2 * math.cos(a), cy + h / 2 * math.sin(a)) for a in ang]
    I = [(cx + ri[0] * math.cos(a) * (1 + rnd.uniform(-.08, .08)), cy + ri[1] * math.sin(a)) for a in ang]
    polys = []
    for k in range(8):
        n = (k + 1) % 8
        polys.append(np.array([O[k], O[n], I[n], I[k]], float))
        polys.append(np.array([I[k], I[n], (cx, cy)], float))
    levels = [1, 3, 2, 4, 0, 2, 3, 1, 4, 2, 1, 0, 3, 4, 2, 1]
    angles = [rnd.choice((0, 30, 60, 90, 120, 150)) for _ in polys]
    return Design(int(w), int(h), polys, levels, angles, [np.array(O, float)], [], [])


def warmup2_page(be, geom: PageGeometry, proj, style: StyleParams, page_no=None):
    s = geom.safe
    wrap = _fonts_wrap()
    y = _title(be, s, wrap, "Warm-Up 2", "Density, simple hatch and cross-hatch.",
               "Practise lighter and darker shading, and spot when a shape wants one direction or two.")
    W = s.w - 12
    x0 = s.x + 6

    # 1. Light / Medium / Dark: o chia cheo, nua duoi-trai da to, nua tren-phai la ky hieu
    y += 26
    heading(be, s, y, 1, "Light, Medium, Dark, Cross-hatch", "The filled half shows what the mark becomes.")
    y += 16
    g = 10.0
    bw, bh = (W - 3 * g) / 4, 84.0
    tones = (("Light", 135, 1), ("Medium", 90, 2), ("Dark", 45, 3), ("Cross-hatch", 20, 4))
    for i, (cap, ang, lv) in enumerate(tones):
        bx = x0 + i * (bw + g)
        tl, tr, br, bl = (bx, y), (bx + bw, y), (bx + bw, y + bh), (bx, y + bh)
        lower = np.array([tl, br, bl], float)
        upper = np.array([tl, tr, br], float)
        fill_in(be, lower, ang, lv, style)
        guides_in(be, upper, ang, lv, style, glen=bw * 0.3)
        outline(be, lower, style, 1.2)
        outline(be, np.array([tl, tr, br, bl], float), style, 1.9)
        be.text(bx + bw / 2, y + bh + 13, cap, 9.5, 0.3, "regular", "middle")
    y += bh + 36

    # 2. Gach don va gach cheo: ky hieu -> ket qua, moi loai 2 vi du
    heading(be, s, y, 2, "Simple hatch and cross-hatch", "Copy the mark, then fill the shape.")
    y += 16
    col_w = (W - 24) / 2
    sw_, sh_ = 96.0, 58.0
    def pair(px, py, nm, ang, lv):
        pa = shape(nm, Box(px, py, sw_, sh_), 2)
        pb = shape(nm, Box(px + sw_ + 30, py, sw_, sh_), 2)
        guides_in(be, pa, ang, lv, style, glen=sw_ * 0.4)
        outline(be, pa, style, 1.6)
        fill_in(be, pb, ang, lv, style)
        outline(be, pb, style, 1.6)
        ay = py + sh_ / 2
        be.lines([((px + sw_ + 6, ay), (px + sw_ + 22, ay)), ((px + sw_ + 22, ay), (px + sw_ + 17, ay - 4)),
                  ((px + sw_ + 22, ay), (px + sw_ + 17, ay + 4))], 0.9, 0.3)
    for c, (title, note, items) in enumerate((
            ("Simple hatch", "one set of lines", (("penta2", 125, 2), ("kite", 80, 1))),
            ("Cross-hatch", "two sets crossing", (("quad", 35, 4), ("pent", 10, 4))))):
        cx0 = x0 + c * (col_w + 24)
        be.text(cx0, y + 4, title, 11.5, 0.05, "bold", "start")
        be.text(cx0 + _tw(title, 11.5, "bold") * 1.1 + 8, y + 4, note, 9.5, 0.4, "italic", "start")
        for r, (nm, ang, lv) in enumerate(items):
            pair(cx0, y + 14 + r * (sh_ + 10), nm, ang, lv)
    y += 14 + 2 * (sh_ + 10) + 24

    # 3. Vien ngoc tong hop
    heading(be, s, y, 3, "Combined facets", "Build contrast slowly, one facet at a time.")
    y += 10
    ph = max(70.0, s.y2 - 22 - 38 - y)
    gw = min(W * 0.62, ph * 1.5)
    box = Box(s.x + s.w / 2 - gw / 2, y, gw, ph)
    draw_design(be, _gem_design(box.w, box.h), box, "page", style)
    be.text(s.x + s.w / 2, s.y2 - 22, "Let the image grow section by section.", 11, 0.1, "italic")
    _footer(be, geom, page_no)


# ----------------------------- Training 1 / 2: tranh that, the nhiem vu o ben trai -----------------------------
TRAIN_SUB = {1: "Your first full drawing.", 2: "Now with a checklist."}
TRAIN_STEPS = {
    1: [("Start with the single-direction facets.", "Grey marks with parallel lines."),
        ("Add the second layer on cross-hatch facets.", "Finish one direction first."),
        ("Leave blank facets white.", "They are the highlights.")],
    2: [("Light tones first, dark tones last.", "Spacing sets the tone."),
        ("Keep every stroke at its facet's angle.", "Turn the book, not your wrist."),
        ("Step back after each section.", "Check the contrast.")],
}


def _facet_by(design, T, pred):
    """Mang lon nhat thoa pred(level), tra ve tam (toa do trang)."""
    best, bc = 0.0, None
    for P, lv in zip(design.polys, design.levels):
        if not pred(lv):
            continue
        poly = Polygon(T(P))
        if not poly.is_valid or poly.area <= best:
            continue
        best = poly.area
        bc = poly.representative_point().coords[0]
    return bc


def training_page(be, geom: PageGeometry, design, style: StyleParams, k=1, page_no=None):
    from .pages import key_scale
    s = geom.safe
    wrap = _fonts_wrap()
    cx = s.x + s.w / 2
    be.text(cx, s.y + 46, f"Training {k}", 32, 0, "bold")
    be.text(cx, s.y + 72, TRAIN_SUB.get(k, ""), 14.5, 0.05, "bold")

    side_w = s.w * 0.27
    x0 = s.x + 6
    y = s.y + 108
    be.rect(x0, y, side_w, 238, stroke=0.45, width=0.8, r=9)
    be.text(x0 + 12, y + 20, "Mission" if k == 1 else "Checklist", 13, 0.05, "bold", "start")
    yy = y + 36
    for i, (head, note) in enumerate(TRAIN_STEPS.get(k, TRAIN_STEPS[1])):
        if k == 1:
            badge(be, x0 + 20, yy + 6, i + 1, 8.0)
        else:
            checkbox(be, x0 + 12, yy - 1, 10)
        tx = x0 + 34
        for ln in wrap(head, 9.5, side_w - 44, "bold"):
            yy += 11.5
            be.text(tx, yy, ln, 9.5, 0.05, "bold", "start")
        for ln in wrap(note, 8.8, side_w - 44, "regular"):
            yy += 11
            be.text(tx, yy, ln, 8.8, 0.35, "regular", "start")
        yy += 12

    # mau da hoan thanh (nho) voi huy hieu so
    pv = Box(x0, y + 252, side_w, s.h * 0.2)
    draw_design(be, design, pv, "key", style, guide_scale=key_scale(design, pv, geom))
    T = fit_transform(design, pv)
    sc, _, oy = fit_params(design, pv)
    _, _, _, y1_ = subject_bbox(design)
    pbot = oy + y1_ * sc
    be.text(x0 + side_w / 2, pbot + 16, "Finished preview", 10.5, 0.15, "italic")
    for n, pred in enumerate((lambda lv: lv in (1, 2, 3), lambda lv: lv == 0, lambda lv: lv == 4), start=1):
        tgt = _facet_by(design, T, pred)
        if tgt is not None:
            be.fill_poly(circle_pts(tgt[0], tgt[1], 6.5), 1.0)
            be.stroke_poly(circle_pts(tgt[0], tgt[1], 6.5), 1.0, 0.1)
            be.text(tgt[0], tgt[1] + 3.5, str(n), 9, 0.05, "bold", "middle")
    ly = pbot + 32
    for n, (nm, note) in enumerate((("Simple hatch", "one direction"), ("Highlight", "leave white"),
                                    ("Shadow", "cross-hatch")), start=1):
        badge(be, x0 + 8, ly - 3, n, 6.5)
        be.text(x0 + 20, ly, f"{nm} \u2013 {note}", 8.8, 0.2, "regular", "start")
        ly += 14

    gx = x0 + side_w + 16
    gbox = Box(gx, s.y + 100, s.x2 - 6 - gx, s.y2 - 40 - (s.y + 100))
    draw_design(be, design, gbox, "page", style)
    be.text(s.x + s.w * 0.64, s.y2 - 22, "Follow the guides. Some facets stay white on purpose.", 11, 0.1, "italic")
    _footer(be, geom, page_no)
