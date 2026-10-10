"""
Ve thiet ke len trang: cung mot ham ve cho ca SVG (xem truoc, xuat Inkscape) va PDF (nop KDP).
Toa do trang: point, goc tren-trai, y huong xuong.
"""
import html
import io
import math
from dataclasses import dataclass, asdict, replace

import numpy as np
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfgen.canvas import FILL_EVEN_ODD
from shapely.geometry import LineString, MultiLineString, Polygon
import shapely
from shapely.ops import polylabel, unary_union

from . import fonts
from .keeps import radial_hatch
from .layout import Box, PageGeometry, PT


@dataclass(frozen=True)
class StyleParams:
    guide_gray: float = 0.91      # vach chua to: xam nhat (0 den .. 1 trang); ~0.7-0.8 van thay ro khi in KDP
    guide_len: float = 15.0       # do dai toi da 3 vach ky hieu (pt)
    guide_min_gap: float = 0.0    # khoang cach vach nho nhat (pt) khi mang qua nho de nhet 3 vach; 0 = tu dong (50% khoang cach net to)
    outline_w: float = 0.6
    silhouette_w: float = 1.3
    hatch_w: float = 0.45
    guide_w: float = 0.40         # vach chua to: mong hon net da to
    trace_w: float = 1.3          # net da to san (mau/huong dan): dam, day hon vach chua to
    trace_gray: float = 0.12
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


def mark_center(poly: Polygon):
    """Tam chung cua mang: ky hieu chua to VA luoi net to deu di qua diem nay => hai trang khop nhau.
    Trong tam neu no nam hop ly trong mang, nguoc lai tam hinh tron noi tiep lon nhat. Tra ve (tam, ban kinh)."""
    rp = polylabel(poly, tolerance=0.05)
    r = poly.exterior.distance(rp)
    cen = poly.centroid
    if poly.contains(cen) and poly.exterior.distance(cen) >= 0.6 * r:
        rp = cen
        r = poly.exterior.distance(cen)
    return np.array(rp.coords[0]), r


def hatch_segments(poly: Polygon, angle, spacing):
    d, n = _dirs(angle)
    c = mark_center(poly)[0]
    minx, miny, maxx, maxy = poly.bounds
    R = math.hypot(maxx - minx, maxy - miny)
    out = []
    k = -R + (R % spacing)
    while k <= R:
        _collect(poly.intersection(LineString([c + n * k - d * R, c + n * k + d * R])), out)
        k += spacing
    return out


def _mark(c, angle, sp, n, L, cross):
    """Ky hieu day du: n vach (1 huong) hoac luoi n x n (gach cheo), can giua tai c."""
    offs = [k - (n - 1) / 2 for k in range(n)]
    segs = []
    for ang in ((angle, angle + 90) if cross else (angle,)):
        d, nn = _dirs(ang)
        for k in offs:
            m = c + nn * k * sp
            segs.append((tuple(m - d * L / 2), tuple(m + d * L / 2)))
    return segs


def guide_segments(poly: Polygon, angle, level, style: StyleParams, scale=1.0, free=None):
    """Ky hieu chua to: LUON day du (3 vach, hoac luoi vuong cho gach cheo), nam giua mang.

    Thu khoang cach that truoc; mang nho thi thu nho khoang cach dan (khong duoi style.guide_min_gap),
    roi thu ngan vach. Neu van khong vua thi ve o co nho nhat tai tam (co the tran nhe ra mep) chu khong bo ky hieu.
    """
    c, r = mark_center(poly)
    cross = level == 4
    true_sp = style.spacing(level) * scale
    gmin = min(style.guide_min_gap * scale, true_sp) if style.guide_min_gap > 0 else 0.5 * true_sp
    pad = min(0.6 * scale, r * 0.25)
    inner = poly.buffer(-pad)
    if free is not None:                      # phan mang con trong sau khi tru vet muc den: ky hieu phai nam gon trong do
        inner = inner.intersection(free.buffer(-0.3 * scale))
    cap = style.guide_len * scale
    sizes = (3,)   # le: cac vach nam tren luoi net to (qua tam); luon du 3 vach / luoi vuong 3x3, khong bao gio dau + hay x
    spacings = [true_sp * (gmin / true_sp) ** (i / 8) for i in range(9)] if gmin < true_sp else [true_sp]
    if not inner.is_empty:
        for n in sizes:
            for sp in spacings:
                Lmax = max(n - 1, 1) * sp * 1.2 + sp * 0.6 if cross else min(cap, 2.0 * r)
                Lmin = (2.0 * sp + 0.4 * scale if n > 1 else 1.2 * sp) if cross else 2.0 * scale
                L = Lmax
                a = math.radians(angle)
                d, nm = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
                while L >= Lmin - 1e-9:
                    # tam goc truoc; neu bi vet muc chan thi truot tam theo luoi net to (van cung goc, cung khoang cach)
                    shifts = [(0.0, 0.0)]
                    if free is not None:
                        if cross:
                            more = [(i * sp, j * sp) for i in (-2, -1, 0, 1, 2) for j in (-2, -1, 0, 1, 2) if i or j]
                        else:
                            st = 0.3 * L
                            more = [(t * st, k * sp) for k in (0, -1, 1, -2, 2) for t in (0, -1, 1, -2, 2) if t or k]
                        shifts += sorted(more, key=lambda q: q[0] ** 2 + q[1] ** 2)
                    for t, k in shifts:
                        segs = _mark(np.asarray(c, float) + t * d + k * nm, angle, sp, n, L, cross)
                        if all(inner.contains(LineString(sg)) for sg in segs):
                            return segs
                    L *= 0.92
    sp = gmin
    L = sp * 1.2 if cross else max(2.0 * scale, min(cap, 2.0 * r))
    return _mark(c, angle, sp, 3, (2 * sp * 1.2 + sp * 0.6) if cross else L, cross)


# ----------------------------- BO PATTERN DUNG CHUNG -----------------------------
# Day la dinh nghia duy nhat cua cac pattern trong "How to Use This Book": vach mau (chua to) va net to.
# Moi trang (huong dan, khoi dong, luyen tap, tranh, dap an) chi goi cac ham nay, khong tu ve rieng.
def fill_segments(poly: Polygon, angle, level, style: StyleParams, scale=1.0):
    """Net to hoan chinh cua mot mang: 1 huong (muc 1-3) hoac 2 huong vuong goc (muc 4)."""
    sp = style.spacing(level) * scale
    segs = hatch_segments(poly, angle, sp)
    if level == 4:
        segs += hatch_segments(poly, angle + 90, sp)
    return segs


def draw_fill(be, poly: Polygon, angle, level, style: StyleParams, scale=1.0, sample=False):
    """sample=True: nu to mau (do dam, manh hon net that); False: net muc that cua tranh/dap an."""
    segs = fill_segments(poly, angle, level, style, scale)
    if sample:
        be.lines(segs, style.trace_w * 0.55, style.trace_gray)
    else:
        be.lines(segs, style.hatch_w, 0.0)


def draw_guide(be, poly: Polygon, angle, level, style: StyleParams, scale=1.0, length=None):
    """Ky hieu chua to o giua mang: 3 vach (1 huong) hoac o luoi 4x4 (gach cheo)."""
    st = replace(style, guide_len=length) if length else style
    be.lines(guide_segments(poly, angle, level, st, scale), style.guide_w, style.guide_gray)


def _valid(P):
    poly = Polygon(P)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly if poly.geom_type == "Polygon" and not poly.is_empty else None


# ----------------------------- ve 1 thiet ke vao 1 khung -----------------------------
def subject_bbox(design):
    """Khung bao cua chu the (x0, y0, x1, y1) theo pixel anh, bo phan nen trang quanh tranh."""
    rings = list(design.silhouette) or list(design.polys)
    if not rings:
        return 0.0, 0.0, float(design.width), float(design.height)
    pts = np.vstack([np.asarray(r, float).reshape(-1, 2) for r in rings])
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    if x1 - x0 < 1 or y1 - y0 < 1:
        return 0.0, 0.0, float(design.width), float(design.height)
    return float(x0), float(y0), float(x1), float(y1)


def fit_params(design, box):
    """(ti le, goc x, goc y) de chu the lap day khung, can giua."""
    x0, y0, x1, y1 = subject_bbox(design)
    s = min(box.w / (x1 - x0), box.h / (y1 - y0))
    ox = box.x + (box.w - (x1 - x0) * s) / 2 - x0 * s
    oy = box.y + (box.h - (y1 - y0) * s) / 2 - y0 * s
    return s, ox, oy


def fit_transform(design, box):
    s, ox, oy = fit_params(design, box)
    return lambda pts: np.asarray(pts) * s + (ox, oy)


def _ink_cover(design, T, page_polys, style):
    """Vung muc den cua tranh (mang den dac, net muc, vet den, net chi tiet) + le nho: ky hieu chua to khong duoc de len."""
    parts = [Polygon(P) for P, lv in zip(page_polys, design.levels) if lv == 5 and len(P) >= 3]
    parts += [Polygon(T(A)) for A in design.accents if len(A) >= 3]
    for rings in getattr(design, "inks", ()):
        if rings and len(rings[0]) >= 3:
            parts.append(Polygon(T(rings[0]), [T(r) for r in rings[1:] if len(r) >= 3]))
    parts += [LineString(T(L)).buffer(style.lineart_w / 2 + 0.6) for L in design.lines if len(L) >= 2]
    parts += [LineString(T(S)).buffer(style.silhouette_w / 2 + 0.6) for S in silhouette_strokes(design)]
    parts = [g.buffer(0.6) if g.is_valid else g.buffer(0).buffer(0.6) for g in parts if not g.is_empty]
    if not parts:
        return None
    cover = unary_union(parts)
    shapely.prepare(cover)
    return cover


def _clip_out(segs, cover, min_len=0.8):
    """Cat bo phan net nam de len vung muc den; bo manh qua ngan."""
    if cover is None:
        return segs
    out = []
    for a, b in segs:
        ls = LineString([a, b])
        if not cover.intersects(ls):
            out.append((a, b))
            continue
        _collect(ls.difference(cover), tmp := [])
        out += [sg for sg in tmp if LineString(sg).length >= min_len]
    return out


def _fallback_guides(poly, free, angle, level, style, scale):
    """Mang bi vet den xe nho: lay chinh cac net to that con thay duoc (phan nam trong vung trong) lam ky hieu,
    nen chac chan khop voi trang dap an. Toi da 3 net dai nhat moi huong, cat gon quanh giua net."""
    cap = style.guide_len * scale
    zone = free.buffer(-0.1 * scale)
    if zone.is_empty:
        return []
    sets = [angle] + ([angle + 90] if level == 4 else [])
    sp = style.spacing(level) * scale
    out = []
    for a in sets:
        cand = []
        for p, q in hatch_segments(poly, a, sp):
            ls = LineString([p, q]).intersection(zone)
            for g in getattr(ls, "geoms", [ls]):
                if g.geom_type == "LineString" and g.length >= 0.8 * scale:
                    cand.append(g)
        cand.sort(key=lambda g: -g.length)
        for g in cand[:3]:
            n = g.length
            t0, t1 = (0.0, n) if n <= cap else ((n - cap) / 2, (n + cap) / 2)
            out.append((tuple(g.interpolate(t0).coords[0]), tuple(g.interpolate(t1).coords[0])))
    return out


def silhouette_strokes(design, edge=2.5):
    """Vien ngoai chu the thanh cac doan ho: bo doan nam doc mep anh (chu the bi cat o mep anh) -> khong ve
    mot duong vien dam thang tap theo khung anh. Anh khong tach duoc nen (vien = ca khung anh) giu nguyen."""
    w, h = design.width, design.height
    out = []
    for S in design.silhouette:
        S = np.asarray(S, float)
        if len(S) < 2:
            continue
        P = np.vstack([S, S[:1]])
        on_edge = (P[:, 0] <= edge) | (P[:, 0] >= w - 1 - edge) | (P[:, 1] <= edge) | (P[:, 1] >= h - 1 - edge)
        seg_edge = on_edge[:-1] & on_edge[1:]           # canh nam tron tren mep anh
        if not seg_edge.any() or seg_edge.all():
            out.append(P)
            continue
        k = int(np.argmax(seg_edge))                    # xoay de bat dau tu mot canh tren mep -> doan khong bi cat doi
        n = len(seg_edge)
        order = [(k + j) % n for j in range(n)]
        run = []
        for j in order:
            if seg_edge[j]:
                if len(run) >= 2:
                    out.append(np.array(run))
                run = []
            else:
                if not run:
                    run.append(P[j])
                run.append(P[j + 1])
        if len(run) >= 2:
            out.append(np.array(run))
    return out


def draw_design(be, design, box: Box, mode: str, style: StyleParams, interactive=False, guide_scale=1.0):
    T = fit_transform(design, box)
    page_polys = [T(p) for p in design.polys]

    be.group("fills")
    for P, lv in zip(page_polys, design.levels):
        if lv == 5:
            be.fill_poly(P, 0.0)
    be.end_group()

    occ = _ink_cover(design, T, page_polys, style) if mode != "key" else None
    hatch, guides = [], []
    for P, lv, ang in zip(page_polys, design.levels, design.angles):
        if lv in (0, 5):
            continue
        poly = _valid(P)
        if poly is None:
            continue
        if mode == "key":
            hatch += fill_segments(poly, ang, lv, style, guide_scale)
        else:
            free = poly.difference(occ) if occ is not None and poly.intersects(occ) else None
            g = _clip_out(guide_segments(poly, ang, lv, style, guide_scale, free), occ)
            if not g and free is not None and not free.is_empty:
                # mang gan nhu bi vet den phu: van phai co ky hieu o phan con trong (cung goc), khong de trang that
                parts = [q for q in getattr(free, "geoms", [free]) if q.geom_type == "Polygon"]
                if parts:
                    big = max(parts, key=lambda q: q.area)
                    g = _clip_out(guide_segments(big, ang, lv, style, guide_scale), occ)
            if free is not None and not free.is_empty and sum(LineString(x).length for x in g) < 4.0 * guide_scale:
                fb = _fallback_guides(poly, free, ang, lv, style, guide_scale)
                if sum(LineString(x).length for x in fb) > sum(LineString(x).length for x in g):
                    g = fb
            guides += g
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
    for S in silhouette_strokes(design):
        be.polyline(T(S), style.silhouette_w, 0.0)
    be.end_group()

    keeps = getattr(design, "keeps", ())
    if keeps:
        be.group("keeps")
        s = fit_params(design, box)[0]
        for kp in keeps:
            draw_keep(be, kp, T, s, style)
        be.end_group()

    if interactive:
        s = fit_params(design, box)[0]
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
