"""
Ve thiet ke len trang: cung mot ham ve cho ca SVG (xem truoc, xuat Inkscape) va PDF (nop KDP).
Toa do trang: point, goc tren-trai, y huong xuong.
"""
import html
import io
import math
from dataclasses import dataclass, asdict

import numpy as np
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfgen.canvas import FILL_EVEN_ODD
from shapely.geometry import LineString, MultiLineString, Polygon

from . import fonts
from .keeps import radial_hatch
from .layout import Box, PageGeometry, PT


@dataclass(frozen=True)
class StyleParams:
    guide_gray: float = 0.58      # 0 den .. 1 trang; ~0.55-0.65 la an toan khi in KDP
    guide_len: float = 15.0       # do dai toi da 3 vach ky hieu (pt)
    outline_w: float = 0.6
    silhouette_w: float = 1.3
    hatch_w: float = 0.45
    guide_w: float = 0.55
    lineart_w: float = 1.1         # net chi tiet (mat, vien hoa tiet) dam hon canh mang
    sp1: float = 6.5              # khoang cach net khi to xong (pt): thua
    sp2: float = 4.2              # vua
    sp3: float = 2.7              # day
    sp4: float = 3.6              # gach cheo (moi lop)

    @staticmethod
    def from_dict(d):
        base = asdict(StyleParams())
        d = d or {}
        return StyleParams(**{k: float(d.get(k, v)) for k, v in base.items()})

    def spacing(self, level):
        return {1: self.sp1, 2: self.sp2, 3: self.sp3, 4: self.sp4}[level]


FONT_CSS = {"regular": ("400", "normal"), "bold": ("700", "normal"), "italic": ("400", "italic")}


# ----------------------------- backends -----------------------------
class SvgBackend:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = []

    @staticmethod
    def _g(v):
        c = int(round(max(0, min(1, v)) * 255))
        return f"#{c:02x}{c:02x}{c:02x}"

    @staticmethod
    def _pts(points):
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)

    def group(self, name):
        self.parts.append(f'<g id="{name}" inkscape:groupmode="layer" inkscape:label="{name}">')

    def end_group(self):
        self.parts.append("</g>")

    def fill_poly(self, points, gray=0.0):
        self.parts.append(f'<polygon points="{self._pts(points)}" fill="{self._g(gray)}"/>')

    def fill_rings(self, rings, gray=0.0):
        d = "".join("M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in r) + "Z" for r in rings)
        self.parts.append(f'<path d="{d}" fill="{self._g(gray)}" fill-rule="evenodd"/>')

    def stroke_poly(self, points, width, gray=0.0):
        self.parts.append(f'<polygon points="{self._pts(points)}" fill="none" stroke="{self._g(gray)}" '
                          f'stroke-width="{width}" stroke-linejoin="round"/>')

    def polyline(self, points, width, gray=0.0):
        self.parts.append(f'<polyline points="{self._pts(points)}" fill="none" stroke="{self._g(gray)}" '
                          f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')

    def lines(self, segs, width, gray=0.0):
        if not segs:
            return
        d = "".join(f"M{x0:.2f} {y0:.2f}L{x1:.2f} {y1:.2f}" for (x0, y0), (x1, y1) in segs)
        self.parts.append(f'<path d="{d}" stroke="{self._g(gray)}" stroke-width="{width}" stroke-linecap="round"/>')

    def rect(self, x, y, w, h, fill=None, stroke=None, width=1.0, r=0.0):
        f = self._g(fill) if fill is not None else "none"
        s = f' stroke="{self._g(stroke)}" stroke-width="{width}"' if stroke is not None else ""
        self.parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{r:.2f}" fill="{f}"{s}/>')

    def text(self, x, y, s, size=9, gray=0.0, style="regular", anchor="middle", rotate=0):
        wt, fs = FONT_CSS[style]
        tr = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate else ""
        self.parts.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" font-weight="{wt}" font-style="{fs}" '
                          f'text-anchor="{anchor}" font-family="Lato, Helvetica, Arial, sans-serif" '
                          f'fill="{self._g(gray)}"{tr}>{html.escape(s)}</text>')

    def hit(self, points, fid, level=0, angle=0):
        self.parts.append(f'<polygon class="hit" data-id="{fid}" data-level="{level}" data-angle="{angle:g}" '
                          f'points="{self._pts(points)}"/>')

    def raw(self, s):
        self.parts.append(s)

    def result(self, physical=False):
        size = (f'width="{self.w / PT:.4f}in" height="{self.h / PT:.4f}in"' if physical
                else f'width="{self.w:.2f}" height="{self.h:.2f}"')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                f'viewBox="0 0 {self.w:.2f} {self.h:.2f}" {size}><rect width="100%" height="100%" fill="#fff"/>'
                + "".join(self.parts) + "</svg>")


class PdfBackend:
    def __init__(self, c, w, h):
        self.c, self.h = c, h
        c.setPageSize((w, h))
        c.setLineCap(1)
        c.setLineJoin(1)

    def _path(self, points, close):
        p = self.c.beginPath()
        x, y = points[0]
        p.moveTo(x, self.h - y)
        for x, y in points[1:]:
            p.lineTo(x, self.h - y)
        if close:
            p.close()
        return p

    def group(self, name):
        pass

    def end_group(self):
        pass

    def fill_poly(self, points, gray=0.0):
        self.c.setFillGray(gray)
        self.c.drawPath(self._path(points, True), fill=1, stroke=0)

    def fill_rings(self, rings, gray=0.0):
        p = self.c.beginPath()
        for r in rings:
            p.moveTo(r[0][0], self.h - r[0][1])
            for x, y in r[1:]:
                p.lineTo(x, self.h - y)
            p.close()
        self.c.setFillGray(gray)
        self.c.drawPath(p, fill=1, stroke=0, fillMode=FILL_EVEN_ODD)

    def stroke_poly(self, points, width, gray=0.0):
        self.c.setStrokeGray(gray)
        self.c.setLineWidth(width)
        self.c.drawPath(self._path(points, True), fill=0, stroke=1)

    def polyline(self, points, width, gray=0.0):
        self.c.setStrokeGray(gray)
        self.c.setLineWidth(width)
        self.c.drawPath(self._path(points, False), fill=0, stroke=1)

    def lines(self, segs, width, gray=0.0):
        if not segs:
            return
        self.c.setStrokeGray(gray)
        self.c.setLineWidth(width)
        self.c.lines([(x0, self.h - y0, x1, self.h - y1) for (x0, y0), (x1, y1) in segs])

    def rect(self, x, y, w, h, fill=None, stroke=None, width=1.0, r=0.0):
        if fill is not None:
            self.c.setFillGray(fill)
        if stroke is not None:
            self.c.setStrokeGray(stroke)
            self.c.setLineWidth(width)
        args = (x, self.h - y - h, w, h)
        kw = dict(fill=int(fill is not None), stroke=int(stroke is not None))
        if r:
            self.c.roundRect(*args, r, **kw)
        else:
            self.c.rect(*args, **kw)

    def text(self, x, y, s, size=9, gray=0.0, style="regular", anchor="middle", rotate=0):
        c = self.c
        c.saveState()
        c.setFont(fonts.pdf_name(style), size)
        c.setFillGray(gray)
        c.translate(x, self.h - y)
        if rotate:
            c.rotate(-rotate)
        {"middle": c.drawCentredString, "start": c.drawString, "end": c.drawRightString}[anchor](0, 0, s)
        c.restoreState()

    def hit(self, points, fid, level=0, angle=0):
        pass

    def raw(self, s):
        pass


# ----------------------------- hinh hoc net -----------------------------
def _dirs(angle_deg):
    a = math.radians(angle_deg)
    d = np.array([math.cos(a), math.sin(a)])
    return d, np.array([-d[1], d[0]])


def _collect(inter, out):
    if inter.is_empty:
        return
    if isinstance(inter, LineString):
        out.append((inter.coords[0], inter.coords[-1]))
    elif isinstance(inter, MultiLineString) or hasattr(inter, "geoms"):
        for g in inter.geoms:
            if isinstance(g, LineString) and not g.is_empty:
                out.append((g.coords[0], g.coords[-1]))


def hatch_segments(poly: Polygon, angle, spacing):
    d, n = _dirs(angle)
    c = np.array(poly.centroid.coords[0])
    minx, miny, maxx, maxy = poly.bounds
    R = math.hypot(maxx - minx, maxy - miny)
    out = []
    k = -R + (R % spacing)
    while k <= R:
        _collect(poly.intersection(LineString([c + n * k - d * R, c + n * k + d * R])), out)
        k += spacing
    return out


def guide_segments(poly: Polygon, angle, level, style: StyleParams, scale=1.0):
    rp = poly.representative_point()
    r = poly.exterior.distance(rp)
    if r < 2.8:
        return []
    inner = poly.buffer(-0.9)
    length = min(style.guide_len * scale, 1.5 * r)
    sp = min((style.spacing(level) if level < 4 else 2.6) * scale, r * 0.45)
    c = np.array(rp.coords[0])
    out = []
    for ang in [angle] + ([angle + 90] if level == 4 else []):
        d, n = _dirs(ang)
        for k in (-1, 0, 1):
            seg = LineString([c + n * k * sp - d * length / 2, c + n * k * sp + d * length / 2])
            _collect(seg.intersection(inner), out)
    return out


def _valid(P):
    poly = Polygon(P)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly if poly.geom_type == "Polygon" and not poly.is_empty else None


# ----------------------------- ve 1 thiet ke vao 1 khung -----------------------------
def fit_transform(design, box):
    s = min(box.w / design.width, box.h / design.height)
    ox = box.x + (box.w - design.width * s) / 2
    oy = box.y + (box.h - design.height * s) / 2
    return lambda pts: np.asarray(pts) * s + (ox, oy)


def draw_design(be, design, box: Box, mode: str, style: StyleParams, interactive=False, guide_scale=1.0):
    T = fit_transform(design, box)
    page_polys = [T(p) for p in design.polys]

    be.group("fills")
    for P, lv in zip(page_polys, design.levels):
        if lv == 5:
            be.fill_poly(P, 0.0)
    be.end_group()

    hatch, guides = [], []
    for P, lv, ang in zip(page_polys, design.levels, design.angles):
        if lv in (0, 5):
            continue
        poly = _valid(P)
        if poly is None:
            continue
        if mode == "key":
            sp = style.spacing(lv) * guide_scale
            hatch += hatch_segments(poly, ang, sp)
            if lv == 4:
                hatch += hatch_segments(poly, ang + 90, sp)
        else:
            guides += guide_segments(poly, ang, lv, style, guide_scale)
    be.group("hatching" if mode == "key" else "guides")
    be.lines(hatch, style.hatch_w, 0.0)
    be.lines(guides, style.guide_w, style.guide_gray)
    be.end_group()

    be.group("details")
    for A in design.accents:
        be.fill_poly(T(A), 0.0)
    for rings in getattr(design, "inks", ()):
        be.fill_rings([T(r) for r in rings], 0.0)
    for L in design.lines:
        be.polyline(T(L), style.lineart_w, 0.0)
    be.end_group()
    be.group("outlines")
    for P in page_polys:
        be.stroke_poly(P, style.outline_w, 0.0)
    for S in design.silhouette:
        be.stroke_poly(T(S), style.silhouette_w, 0.0)
    be.end_group()

    keeps = getattr(design, "keeps", ())
    if keeps:
        be.group("keeps")
        s = min(box.w / design.width, box.h / design.height)
        for kp in keeps:
            draw_keep(be, kp, T, s, style)
        be.end_group()

    if interactive:
        s = min(box.w / design.width, box.h / design.height)
        ox, oy = T([[0.0, 0.0]])[0]
        # de giao dien doi diem bam (toa do trang) -> pixel anh khi them vung giu nguyen
        be.raw(f'<g class="artmap" data-s="{s:.6f}" data-ox="{ox:.3f}" data-oy="{oy:.3f}"></g>')
        be.raw('<g class="keephits">')
        for kp in keeps:
            be.raw(f'<polygon class="keephit" data-keep="{kp["id"]}" points="{SvgBackend._pts(T(kp["ring"]))}"/>')
        be.raw("</g>")
        be.raw('<g class="hits">')
        for P, fid, lv, ang in zip(page_polys, design.ids, design.levels, design.angles):
            be.hit(P, fid, lv, ang)
        be.raw("</g>")


KEEP_DENSE = 1.3     # khoang cach gach nan hoa (pt, do o mep vung): tong toi
KEEP_SPARSE = 2.6    # tong sang hon


def draw_keep(be, kp, T, s, style: StyleParams):
    """Vung giu nguyen: phu trang (an mang/net ben duoi) roi ve lai tu anh goc bang trang den."""
    ring = T(kp["ring"])
    be.fill_poly(ring, 1.0)
    for rings in kp["black"]:
        be.fill_rings([T(r) for r in rings], 0.0)
    c = T([kp["center"]])[0]
    radius = float(np.max(np.hypot(*(ring - c).T)))
    seg = []
    for key, sp in (("dense", KEEP_DENSE), ("sparse", KEEP_SPARSE)):
        seg += radial_hatch([[T(r) for r in rings] for rings in kp[key]], c, sp, radius)
    be.lines(seg, style.hatch_w * 0.8, 0.0)


# ----------------------------- 1 trang tranh hoan chinh -----------------------------
FRAME_IN = 0.18     # do day khung den tinh tu vung an toan vao trong


def design_page(be, design, geom: PageGeometry, mode, style, frame=False, page_no=None,
                label=None, interactive=False):
    """Trang tranh: (khung den tran le) + tranh + so trang. Moi chu nam trong vung an toan."""
    s = geom.safe
    pad = geom.content.x - s.x
    num_h = 16.0 if (page_no or label) else 0.0
    if frame:
        outer = Box(0, 0, geom.page_w, geom.page_h) if geom.bleed else s
        be.group("frame")
        be.rect(outer.x, outer.y, outer.w, outer.h, fill=0.0)
        f = FRAME_IN * PT
        panel = Box(s.x + f, s.y + f, s.w - 2 * f, s.h - 2 * f - num_h)
        be.rect(panel.x, panel.y, panel.w, panel.h, fill=1.0, r=10)
        be.end_group()
        art = Box(panel.x + pad, panel.y + pad, panel.w - 2 * pad, panel.h - 2 * pad)
        text_gray = 1.0
    else:
        c = geom.content
        art = Box(c.x, c.y, c.w, c.h - num_h)
        text_gray = 0.35
    draw_design(be, design, art, mode, style, interactive)
    foot = " · ".join(x for x in (label, str(page_no) if page_no else None) if x)
    if foot:
        be.text(s.x + s.w / 2, s.y2 - 4, foot, 8.5, text_gray)


def overlay_guides(be: SvgBackend, geom: PageGeometry):
    """Chi dung cho xem truoc: vung bleed, duong cat, vung an toan, vung tranh."""
    t, s, c = geom.trim, geom.safe, geom.content
    W, H = geom.page_w, geom.page_h
    be.raw('<g class="guides" pointer-events="none">')
    if geom.bleed:
        be.raw(f'<path d="M0 0H{W}V{H}H0Z M{t.x} {t.y}V{t.y2}H{t.x2}V{t.y}Z" '
               f'fill="#e0484d" fill-opacity="0.16" fill-rule="evenodd"/>')
    be.raw(f'<rect x="{t.x}" y="{t.y}" width="{t.w}" height="{t.h}" fill="none" stroke="#e0484d" stroke-width="0.8"/>')
    be.raw(f'<rect x="{s.x}" y="{s.y}" width="{s.w}" height="{s.h}" fill="none" stroke="#1f8fc4" '
           f'stroke-width="0.8" stroke-dasharray="4 3"/>')
    be.raw(f'<rect x="{c.x}" y="{c.y}" width="{c.w}" height="{c.h}" fill="none" stroke="#2f9e5b" '
           f'stroke-width="0.6" stroke-dasharray="1.5 2.5"/>')
    gx = t.x if geom.side == "right" else t.x2
    be.raw(f'<line x1="{gx}" y1="{t.y}" x2="{gx}" y2="{t.y2}" stroke="#7a5cc7" stroke-width="2.2" stroke-opacity="0.55"/>')
    be.raw("</g>")


def render_svg(design, geom, mode, style, show_guides=True, frame=False, interactive=False,
               page_no=None, physical=False):
    be = SvgBackend(geom.page_w, geom.page_h)
    design_page(be, design, geom, mode, style, frame, page_no, interactive=interactive)
    if show_guides:
        overlay_guides(be, geom)
    return be.result(physical)


def render_pdf(draw_fns, title="Hatch Studio", author=""):
    """draw_fns: list cua (page_w, page_h, fn(be)). Moi phan tu la 1 trang."""
    fonts.register()
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, initialFontName=fonts.pdf_name("regular"), initialFontSize=10)
    c.setTitle(title)
    c.setAuthor(author)
    c.setCreator("Hatch Studio")
    for w, h, fn in draw_fns:
        be = PdfBackend(c, w, h)
        fn(be)
        c.showPage()
    c.save()
    return buf.getvalue()
