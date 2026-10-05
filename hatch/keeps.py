"""
Vung giu nguyen (mat...): khong chia mang, ve lai tu anh goc bang trang den.
  - den dac: phan rat toi (con nguoi, vien mi)
  - gach nan hoa toa tu tam: tong trung binh (mong mat), 2 muc day/thua
  - trang: phan sang (diem bat sang, long trang)

Tu dong tim mat theo diem bat sang (catchlight) nam tren khoi toi day, tron; nguoi dung them/bot tay.
Moi toa do tinh theo pixel anh.
"""
import math

import cv2
import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

BLACK, DENSE, SPARSE = 60, 115, 170     # nguong do sang (0-255) cua 3 muc ve trong vung giu
DEBUG = None                            # list -> ghi ly do loai tung diem sang (de tinh chinh)


def _why(msg):
    if DEBUG is not None:
        DEBUG.append(msg)
    return None


def _fill_holes(m):
    inv = np.pad(1 - m, 1, constant_values=1).astype(np.uint8)
    cv2.floodFill(inv, None, (0, 0), 2)
    return (inv[1:-1, 1:-1] != 2).astype(np.uint8)


def _blob(dark, px, py, scales, rh):
    """Mo hinh thai hoc tu co lon xuong nho; tra ve khoi dau tien chua (px, py) ma khong cham mep cua so."""
    for s in scales:
        if s * 2 < 3 * rh:
            break
        o = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * s + 1,) * 2))
        _, bl = cv2.connectedComponents(o, connectivity=4)
        c = bl[py, px]
        if c == 0:
            continue
        b = (bl == c).astype(np.uint8)
        if b[0].any() or b[-1].any() or b[:, 0].any() or b[:, -1].any():
            continue
        return b
    return None


def _grow_white(comp, ink, gi, si, re):
    """Mo rong khoi mong mat ra long trang: chi nhan mang sang, it mau, cham sat mong mat va trong ban kinh
    re (long quanh mat bi vanh mi toi ngan cach nen khong lan sang nep mi / long may)."""
    near = cv2.dilate(comp, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(re) + 1,) * 2))
    white = ((1 - ink) & (1 - comp) & near & (gi > 120) & (si < 60)).astype(np.uint8)
    touch = cv2.dilate(comp, np.ones((5, 5), np.uint8))
    n, bl = cv2.connectedComponents(white, connectivity=4)
    keep = comp.copy()
    for c in range(1, n):
        b = bl == c
        if (touch[b] > 0).any():
            keep[b] = 1
    if keep.sum() == comp.sum():
        return comp
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    return _fill_holes(cv2.morphologyEx(keep, cv2.MORPH_CLOSE, k) & near | comp)


def _shape(comp):
    A = int(comp.sum())
    cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea)
    return A, cnt, A / max(cv2.contourArea(cv2.convexHull(cnt)), 1), math.sqrt(A / math.pi)


def _concentric(gi, comp, px, py, re):
    """Mat: con nguoi (khoi toi) nam giua khoi, diem sang nam tren con nguoi/mong mat; mui (lo mui lech),
    mang long toi co soi trang (nhieu trang, diem sang sat mep) thi khong."""
    M = cv2.moments(comp, True)
    cx, cy = M['m10'] / M['m00'], M['m01'] / M['m00']
    Md = cv2.moments(((gi < 60) & (comp > 0)).astype(np.uint8), True)
    dx, dy = Md['m10'] / Md['m00'], Md['m01'] / Md['m00']
    off, hl_off, white = np.hypot(dx - cx, dy - cy) / re, np.hypot(px - cx, py - cy) / re, (gi[comp > 0] > 210).mean()
    if off > 0.18 or hl_off > 0.7 or white > 0.2:
        return _why(f'not concentric pupil={off:.2f} hl={hl_off:.2f} white={white:.2f}')
    return True


def _eye_at(win, px, py, rh, scales, max_re, enclosed):
    """Thu tim mat quanh diem sang (px, py) trong cua so; tra ve (khoi, vien) hoac None."""
    gi, si, mi, ink = win
    comp = _blob(_fill_holes(ink), px, py, scales, rh)
    if comp is None:
        return _why('no blob')
    A, cnt, solid, re = _shape(comp)
    k = int(re / 2) | 1
    ring = cv2.dilate(comp, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) & (1 - comp)
    if not ring.any() or mi[ring > 0].mean() < 0.8:            # mat nam trong than, khong sat nen
        return _why('edge of subject')
    if not (solid > 0.8 and 2.5 * rh < re < max_re and (gi[comp > 0] < 60).mean() > 0.15):
        return _why(f'shape solid={solid:.2f} re={re:.1f} rh={rh} dark={(gi[comp > 0] < 60).mean():.2f}')
    if not _concentric(gi, comp, px, py, re):
        return None
    if not enclosed:
        con = float(np.median(gi[ring > 0])) - float(np.median(gi[comp > 0]))
        return (comp, cnt) if con > 80 else _why(f'contrast {con:.0f}')
    # vung vien muc kin: ruot (mong mat) la mang lien, tong trung binh (khong phai giay trang giua net gach),
    # con nguoi la khoi muc tron quanh diem sang, khong chiem het
    inner = ((comp > 0) & (ink == 0)).astype(np.uint8)
    if solid < 0.85 or inner.sum() < 0.25 * A or not 25 < np.median(gi[inner > 0]) < 170:
        return _why(f'inner solid={solid:.2f} frac={inner.sum() / A:.2f} med={np.median(gi[inner > 0]) if inner.any() else -1}')
    n, _, st, _ = cv2.connectedComponentsWithStats(inner, connectivity=8)
    if n - 1 > 6 or st[1:, 4].max() < 0.6 * inner.sum():          # net gach cheo -> nhieu manh vun
        return _why(f'fragmented n={n - 1}')
    core = _blob(ink & comp, px, py, [max(2, int(rh))], 0)
    if core is None or not 0.2 * A < core.sum() < 0.6 * A:
        return _why(f'core {None if core is None else core.sum() / A}')
    comp = _grow_white(comp, ink, gi, si, re)
    return comp, _shape(comp)[1]


def find_eyes(img, mask):
    """Tra ve list (cx, cy, contour) cac mat tim duoc.
    Mat = khoi toi day quanh 1 diem bat sang: mo hinh thai hoc o nhieu co, co lon nhat con giu
    duoc khoi chua diem sang ma khong tran ra ngoai la hinh mat (long mi, nep da mong bi loai).
    Luot 2 cho con vat long toi (gorilla...), mong mat toi ngang long xung quanh: chi lay net muc rat toi
    + lap lo -> vung duoc vien muc khep kin, xet theo cau truc thay vi do tuong phan voi xung quanh."""
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 1]
    h, w = g.shape
    side = max(h, w)
    hl = ((g > 210) & (sat < 70) & (mask > 0)).astype(np.uint8)
    n, lab_hl, st, cen = cv2.connectedComponentsWithStats(hl)
    small = np.r_[False, (st[1:, 4] >= 3) & (st[1:, 4] <= (side * 0.03) ** 2)]
    # chi diem sang co co diem bat sang moi tinh vao khoi mat (mang long trang lon thi khong)
    hl_d = cv2.dilate(small[lab_hl].astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    passes = [(False, ((g < 110) | hl_d).astype(np.uint8))] + \
             [(True, ((g < t) | hl_d).astype(np.uint8)) for t in (30, 20)]
    R = int(side * 0.07)
    scales = [max(2, int(side * f)) for f in (0.03, 0.022, 0.016, 0.012, 0.009, 0.007)]
    taken = np.zeros((h, w), np.uint8)
    # loc nhanh: diem sang nho, nam tren nen toi; xet truoc cac diem toi nhat, toi da 60 diem (anh line art
    # co hang nghin khe trang giua cac net)
    cands = []
    for i in range(1, n):
        if not small[i]:
            continue
        bw, bh = st[i, 2], st[i, 3]
        cx, cy = int(cen[i][0]), int(cen[i][1])
        rh = max(bw, bh) / 2
        q = int(2.5 * rh + 4)
        dark_frac = (g[max(cy - q, 0):cy + q + 1, max(cx - q, 0):cx + q + 1] < 60).mean()
        if dark_frac >= 0.3 and mask[cy, cx]:
            cands.append((dark_frac, cx, cy, rh))
    cands = sorted(cands, reverse=True)[:60]
    out = []
    # luot thuong chay het cac diem truoc, luot vien kin chi xet cac diem con lai
    for enclosed, src in passes:
        for _, cx, cy, rh in cands:
            if taken[cy, cx]:
                continue
            x0, x1, y0, y1 = max(cx - R, 0), min(cx + R + 1, w), max(cy - R, 0), min(cy + R + 1, h)
            win = (g[y0:y1, x0:x1], sat[y0:y1, x0:x1], mask[y0:y1, x0:x1], src[y0:y1, x0:x1])
            _why((cx, cy, rh, enclosed))
            found = _eye_at(win, cx - x0, cy - y0, rh, scales, side * 0.06, enclosed)
            if found is None:
                continue
            comp, cnt = found
            taken[y0:y1, x0:x1] |= cv2.dilate(comp, np.ones((5, 5), np.uint8))
            c = cv2.approxPolyDP(cnt, 1.0, True)[:, 0, :].astype(float) + (x0, y0)
            out.append((float(cx), float(cy), c))
    return out


def _rings(binary, x0, y0, min_area=4):
    """Anh nhi phan -> list [vien ngoai, lo...] (toa do anh), da lam tron."""
    from .engine import _chaikin
    out = []
    cnts, hier = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    for i, c in enumerate(cnts):
        if hier[0][i][3] >= 0 or cv2.contourArea(c) < min_area:
            continue
        rings = []
        for j in [i] + [j for j in range(len(cnts)) if hier[0][j][3] == i and cv2.contourArea(cnts[j]) >= min_area]:
            a = cv2.approxPolyDP(cnts[j], 0.7, True)[:, 0, :].astype(float)
            if len(a) >= 3:
                rings.append(_chaikin(a, True) + (x0, y0))
        if rings:
            out.append(rings)
    return out


def keep_art(gray, ring):
    """Vung (ring, toa do anh) -> cac lop ve trang den lay tu anh goc."""
    h, w = gray.shape
    ring = np.asarray(ring, float)
    x0, y0 = np.maximum(np.floor(ring.min(axis=0)).astype(int) - 2, 0)
    x1, y1 = np.minimum(np.ceil(ring.max(axis=0)).astype(int) + 3, (w, h))
    region = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillPoly(region, [np.round(ring - (x0, y0)).astype(np.int32)], 1)
    g = cv2.bilateralFilter(gray[y0:y1, x0:x1], 5, 40, 5)
    tone = lambda lo, hi: (((g >= lo) & (g < hi)) & (region > 0)).astype(np.uint8)
    # nguong theo tung vung: den chi danh cho con nguoi/vien (phan toi nhat), mong mat toi van gach net
    t_black, t_dense = BLACK, DENSE
    dark = g[(region > 0) & (g < SPARSE)]
    if dark.size > 30:
        t, _ = cv2.threshold(dark.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        darker = dark[dark < t]
        if darker.size > 30:            # Otsu lan 2 trong phan toi: tach con nguoi khoi mong mat toi (gorilla)
            t, _ = cv2.threshold(darker.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        t_black = float(np.clip(t, 12, 30))
        t_dense = t_black + (SPARSE - t_black) * 0.45
    poly = Polygon(ring).buffer(0)
    c = poly.centroid
    return {
        "ring": ring,
        "center": (c.x, c.y),
        "black": _rings(tone(0, t_black), x0, y0),
        "dense": _rings(tone(t_black, t_dense), x0, y0, 8),
        "sparse": _rings(tone(t_dense, SPARSE), x0, y0, 8),
    }


def circle(cx, cy, r, n=48):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.c_[cx + r * np.cos(t), cy + r * np.sin(t)]


def _geom(ring_lists):
    polys = []
    for rings in ring_lists:
        p = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3])
        polys.append(p if p.is_valid else p.buffer(0))
    return unary_union(polys) if polys else Polygon()


def radial_hatch(ring_lists, center, spacing, radius):
    """Gach nan hoa toa tu tam, cat theo vung (toa do trang). spacing do o mep vung."""
    geom = _geom(ring_lists)
    if geom.is_empty:
        return []
    n = max(12, int(2 * math.pi * radius / spacing))
    cx, cy = center
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        ray = LineString([(cx, cy), (cx + 2 * radius * math.cos(a), cy + 2 * radius * math.sin(a))])
        inter = geom.intersection(ray)
        for s in getattr(inter, "geoms", [inter]):
            if s.geom_type == "LineString" and not s.is_empty and s.length > 0.3:
                out.append((s.coords[0], s.coords[-1]))
    return out
