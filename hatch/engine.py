"""
Engine: anh -> thiet ke low-poly co muc sang toi + huong net cho tung mang.

Moi toa do o day tinh theo pixel anh (goc tren-trai, y huong xuong).
Phan ve ra trang (render.py) se co gian vao vung noi dung cua trang in.
"""
import math
import random
from dataclasses import dataclass, field, asdict

import cv2
import numpy as np
from scipy.spatial import Delaunay
from shapely.geometry import Polygon
from shapely.ops import unary_union

MAX_SIDE = 1400


@dataclass(frozen=True)
class EngineParams:
    facets: int = 260          # so diem ngau nhien (so mang thuc te ~ 1.5-2.5 lan)
    merge: float = 0.5         # ti le gop 2 tam giac thanh tu giac
    lineart: float = 0.08      # do dai toi thieu cua net chi tiet (ti le), 0 = tat
    accents: bool = True       # to den san vung rat toi (mat, mui)
    grabcut: bool = False      # tu tach nen
    white: float = 0.14        # ti le mang de trang
    black: float = 0.035       # ti le mang to den dac
    min_angle_gap: int = 30    # 2 mang ke nhau lech huong toi thieu (do)
    seed: int = 7

    @staticmethod
    def from_dict(d):
        base = asdict(EngineParams())
        out = {}
        for k, v in base.items():
            if k in d and d[k] is not None:
                out[k] = type(v)(d[k]) if not isinstance(v, bool) else str(d[k]).lower() in ("1", "true", "on", "yes")
        return EngineParams(**{**base, **out})


@dataclass
class Design:
    width: int
    height: int
    polys: list            # list[np.ndarray (k,2)] da giac moi mang
    levels: list           # 0 trang, 1 thua, 2 vua, 3 day, 4 gach cheo, 5 den dac
    angles: list           # do, 0-180
    silhouette: list       # list[np.ndarray] vien ngoai chu the
    accents: list          # list[np.ndarray] vung to den san
    lines: list            # list[np.ndarray] net chi tiet (polyline)
    stats: dict = field(default_factory=dict)
    ids: list = None       # id on dinh cua tung mang ("f12", "f12a"...) de luu chinh sua tay

    def __post_init__(self):
        if self.ids is None:
            self.ids = [f"f{i}" for i in range(len(self.polys))]


# --------------------------------------------------------------------------
def decode_image(data: bytes):
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Khong doc duoc anh. Hay dung PNG hoac JPG.")
    alpha = None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        alpha = img[:, :, 3]
        img = img[:, :, :3]
    s = MAX_SIDE / max(img.shape[:2])
    if s < 1:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        if alpha is not None:
            alpha = cv2.resize(alpha, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
    return img, alpha


def subject_mask(img, alpha, use_grabcut):
    h, w = img.shape[:2]
    if alpha is not None and (alpha < 250).any():
        m = (alpha > 127).astype(np.uint8)
    elif use_grabcut:
        m = np.zeros((h, w), np.uint8)
        rect = (int(w * 0.04), int(h * 0.04), int(w * 0.92), int(h * 0.92))
        bg, fg = np.zeros((1, 65)), np.zeros((1, 65))
        cv2.grabCut(img, m, rect, bg, fg, 5, cv2.GC_INIT_WITH_RECT)
        m = np.where((m == 1) | (m == 3), 1, 0).astype(np.uint8)
    else:
        return np.ones((h, w), np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        m = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    if m.sum() < 0.02 * h * w:          # tach nen that bai -> dung ca anh
        return np.ones((h, w), np.uint8)
    return m


def edge_polylines(gray, mask, min_len, eps=2.0):
    g = cv2.bilateralFilter(gray, 9, 60, 9)
    v = float(np.median(g))
    edges = cv2.Canny(g, int(max(0, 0.66 * v)), int(min(255, 1.33 * v)))
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8)) & (mask * 255)
    cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cnts:
        if cv2.arcLength(c, False) / 2 < min_len:
            continue
        out.append(cv2.approxPolyDP(c, eps, False)[:, 0, :].astype(float))
    out.sort(key=lambda p: -len(p))
    return out


def sample_points(gray, mask, n_points, rng):
    h, w = gray.shape
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.GaussianBlur(np.hypot(gx, gy), (0, 0), 3)
    weight = ((edge / (edge.max() + 1e-6)) ** 0.8 + 0.12) * mask
    prob = (weight / weight.sum()).ravel()

    min_d = 0.45 * math.sqrt(mask.sum() / n_points)
    cell = max(min_d, 1.0)
    grid, pts = {}, []

    def far_enough(x, y, d):
        gi, gj = int(x // cell), int(y // cell)
        r = int(math.ceil(d / cell))
        for i in range(gi - r, gi + r + 1):
            for j in range(gj - r, gj + r + 1):
                for px, py in grid.get((i, j), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < d * d:
                        return False
        return True

    def add(x, y):
        pts.append((x, y))
        grid.setdefault((int(x // cell), int(y // cell)), []).append((x, y))

    # 1) vien chu the
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea)
    approx = cv2.approxPolyDP(cnt, 0.004 * cv2.arcLength(cnt, True), True)[:, 0, :]
    for x, y in approx:
        add(float(x), float(y))
    if mask.all():
        step = 2.2 * min_d
        for t in np.arange(step, w - 1, step):
            add(float(t), 0.0); add(float(t), h - 1.0)
        for t in np.arange(step, h - 1, step):
            add(0.0, float(t)); add(w - 1.0, float(t))

    # 2) diem tren cac net chinh -> mang bam theo chi tiet (mat, mieng...)
    for pl in edge_polylines(gray, mask, 0.12 * math.sqrt(mask.sum()))[:25]:
        for x, y in pl[::3]:
            if far_enough(x, y, 0.8 * min_d):
                add(float(x), float(y))

    # 3) diem ngau nhien theo trong so
    target = len(pts) + n_points
    for idx in rng.choice(h * w, size=n_points * 6, p=prob):
        y, x = divmod(int(idx), w)
        if far_enough(x, y, min_d):
            add(float(x), float(y))
            if len(pts) >= target:
                break
    return np.array(pts, dtype=np.float64), approx


def build_facets(pts, mask, gray_blur, merge_ratio, seed):
    rnd = random.Random(seed)
    tri = Delaunay(pts)
    h, w = mask.shape

    tris = []
    for s in tri.simplices:
        p = pts[s]
        u, v = p[1] - p[0], p[2] - p[0]
        area = abs(u[0] * v[1] - u[1] * v[0]) / 2      # np.cross 2D bi bo tu NumPy 2
        if area < 4:
            continue
        cx, cy = p.mean(axis=0)
        if mask[min(int(cy), h - 1), min(int(cx), w - 1)]:
            tris.append(tuple(int(i) for i in s))

    # do sang trung binh: ve nhan id vao 1 anh roi bincount (nhanh)
    label = np.full((h, w), -1, np.int32)
    for i, s in enumerate(tris):
        cv2.fillPoly(label, [pts[list(s)].astype(np.int32)], int(i))
    valid = label >= 0
    sums = np.bincount(label[valid], weights=gray_blur[valid], minlength=len(tris))
    cnts = np.bincount(label[valid], minlength=len(tris))
    tones = np.where(cnts > 0, sums / np.maximum(cnts, 1), 255.0)
    areas = np.maximum(cnts, 1)

    edge_map = {}
    for i, s in enumerate(tris):
        for a, b in ((s[0], s[1]), (s[1], s[2]), (s[2], s[0])):
            edge_map.setdefault((min(a, b), max(a, b)), []).append(i)

    group = list(range(len(tris)))
    used = set()
    pairs = sorted((abs(tones[v[0]] - tones[v[1]]), v[0], v[1]) for v in edge_map.values() if len(v) == 2)
    for diff, i, j in pairs:
        if diff > 18 or i in used or j in used or rnd.random() > merge_ratio:
            continue
        u = Polygon(pts[list(tris[i])]).union(Polygon(pts[list(tris[j])]))
        if u.geom_type == "Polygon" and u.convex_hull.area - u.area < 0.01 * u.area:
            group[j] = i
            used.update((i, j))

    members_of = {}
    for i in range(len(tris)):
        members_of.setdefault(group[i], []).append(i)

    polys, ftones, tri2f = [], [], {}
    for members in members_of.values():
        if len(members) == 1:
            geom = Polygon(pts[list(tris[members[0]])])
        else:
            geom = unary_union([Polygon(pts[list(tris[k])]) for k in members]).simplify(0.01)
            if geom.geom_type != "Polygon":
                geom = max(geom.geoms, key=lambda g: g.area)
        a = areas[members]
        ftones.append(float((tones[members] * a).sum() / a.sum()))
        for k in members:
            tri2f[k] = len(polys)
        polys.append(np.array(geom.exterior.coords)[:-1])

    nbrs = [set() for _ in polys]
    for v in edge_map.values():
        if len(v) == 2:
            a, b = tri2f[v[0]], tri2f[v[1]]
            if a != b:
                nbrs[a].add(b)
                nbrs[b].add(a)
    return polys, np.array(ftones), nbrs


def assign_levels(tones, white, black):
    white = min(max(white, 0.0), 0.6)
    black = min(max(black, 0.0), 0.3)
    mid = max(1.0 - white - black, 0.05)
    bounds = [white, white + mid * 0.27, white + mid * 0.52, white + mid * 0.78, 1.0 - black]
    n = len(tones)
    levels = np.zeros(n, int)
    for rank, idx in enumerate(np.argsort(-tones)):     # sang nhat truoc
        q = rank / max(n - 1, 1)
        levels[idx] = int(np.searchsorted(bounds, q, side="right"))
    return np.clip(levels, 0, 5)


def assign_angles(polys, levels, nbrs, gap):
    def diff(a, b):
        d = abs(a - b) % 180
        return min(d, 180 - d)

    angles = [None] * len(polys)
    areas = [Polygon(p).area for p in polys]
    for i in sorted(range(len(polys)), key=lambda k: -areas[k]):
        p = polys[i]
        e = np.roll(p, -1, axis=0) - p
        k = int(np.argmax((e ** 2).sum(axis=1)))
        base = math.degrees(math.atan2(e[k, 1], e[k, 0])) % 180
        base = round(base / 15) * 15 % 180
        chosen = base
        for c in [base] + [(base + d) % 180 for d in (45, -45, 90, 30, -30, 60, -60, 15, -15)]:
            if all(angles[j] is None or levels[j] in (0, 5) or diff(c, angles[j]) >= gap for j in nbrs[i]):
                chosen = c
                break
        angles[i] = float(chosen)
    return angles


def dark_accents(gray_blur, mask):
    inside = gray_blur[mask > 0]
    thr = min(45.0, float(np.percentile(inside, 2.5)))
    b = ((gray_blur <= thr) & (mask > 0)).astype(np.uint8)
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total = mask.sum()
    out = []
    for c in cnts:
        if 25 < cv2.contourArea(c) < 0.015 * total:
            c = cv2.approxPolyDP(c, 1.2, True)
            if len(c) >= 3:
                out.append(c[:, 0, :].astype(float))
    return out


def make_design(image_bytes: bytes, params: EngineParams) -> Design:
    img, alpha = decode_image(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    mask = subject_mask(img, alpha, params.grabcut)
    gray_blur = cv2.GaussianBlur(gray, (0, 0), 2).astype(np.float64)
    rng = np.random.default_rng(params.seed)

    pts, _ = sample_points(gray, mask, max(params.facets, 30), rng)
    polys, tones, nbrs = build_facets(pts, mask, gray_blur, params.merge, params.seed)
    levels = assign_levels(tones, params.white, params.black)
    angles = assign_angles(polys, levels, nbrs, params.min_angle_gap)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    sil = [cv2.approxPolyDP(c, 1.0, True)[:, 0, :].astype(float)
           for c in cnts if cv2.contourArea(c) > 100]

    accents = dark_accents(gray_blur, mask) if params.accents else []
    lines = (edge_polylines(gray, mask, params.lineart * math.sqrt(mask.sum()), eps=1.5)
             if params.lineart > 0 else [])

    h, w = gray.shape
    stats = {
        "facets": len(polys),
        "levels": {str(lv): int((levels == lv).sum()) for lv in range(6)},
        "image_px": [w, h],
    }
    return Design(w, h, polys, [int(x) for x in levels], angles, sil, accents, lines, stats)
