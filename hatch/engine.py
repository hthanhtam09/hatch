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
import shapely
import shapely.affinity
from scipy.spatial import Delaunay
from shapely.geometry import LineString, Polygon
from shapely.ops import polylabel, split, unary_union

from .keeps import find_eyes, keep_art

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
    min_cell: float = 7.0      # ban kinh toi thieu cua mang (pt tren trang): mang nho hon bi gop vao mang ke de du cho ve pattern
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
    inks: list = field(default_factory=list)   # net muc giu do day: moi phan tu = [vien ngoai, lo...]
    keeps: list = field(default_factory=list)  # vung giu nguyen (mat): dict tu keeps.keep_art + "id"
    gray: object = None    # anh xam goc (uint8) de ve vung giu nguyen them bang tay

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


def _border_background(img):
    """Nen phang/chuyen mau nhe cham vien anh (tranh hoat hinh, anh chup nen tron) -> mask chu the."""
    h, w = img.shape[:2]
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 1.5), cv2.COLOR_BGR2LAB).astype(np.float32)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    # mau nen = mau pho bien nhat tren vien (khong lay trung vi: chu the cham nhieu canh anh
    # thi trung vi roi vao mau chu the); du khi nen chi chiem ~1/3 vien anh
    keys, cnt = np.unique((border // 8).astype(np.int32), axis=0, return_counts=True)
    near = np.linalg.norm(border - (keys[cnt.argmax()] * 8 + 4), axis=1) < 14
    ref = border[near].mean(axis=0)
    dist = np.linalg.norm(border - ref, axis=1)
    # nen trang tinh (giay) chi can chiem ~10% vien anh (chu the cat sat mep: nen chi con 1 goc)
    white = ref[0] > 245 and abs(ref[1] - 128) < 4 and abs(ref[2] - 128) < 4
    if (dist < 14).mean() < (0.1 if white else 0.3):
        return None                             # vien anh khong co mau nen ro rang
    # mau gan mau nen VA noi lien voi vien anh; so sanh voi mau nen co dinh (khong loang dan
    # theo pixel ke ben) de khong tran qua canh mem vao trong chu the. Nguong theo do nhieu cua
    # nen: nen phang (tranh AI) nguong chat de giu mang trang cua chu the cham mep anh
    # (nguc/ma trang), nen anh chup (giay, bong do) nguong rong hon
    thr = float(np.clip(2.5 * np.median(dist[dist < 14]) + 3, 6, 20))
    cand = (np.linalg.norm(lab - ref, axis=2) < thr).astype(np.uint8)
    cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab_ids = cv2.connectedComponents(cand, connectivity=4)
    edge_ids = np.unique(np.concatenate([lab_ids[0], lab_ids[-1], lab_ids[:, 0], lab_ids[:, -1]]))
    bg = np.isin(lab_ids, edge_ids[edge_ids > 0])
    m = (~bg).astype(np.uint8)
    return m if 0.08 < m.mean() < 0.97 else None


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
        m = _border_background(img)
        if m is None:
            return np.ones((h, w), np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        m = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    if m.sum() < 0.02 * h * w:          # tach nen that bai -> dung ca anh
        return np.ones((h, w), np.uint8)
    return m


# ----------------------------- net chi tiet -----------------------------
# Moi net ve trong anh (net muc hoat hinh hay canh sang/toi) chi thanh MOT duong tam,
# khong phai duong bao quanh net (duong bao cho ra 2-4 net song song, rang cua).
def _ring(img):
    P = np.pad(img, 1)
    return [P[:-2, 1:-1], P[:-2, 2:], P[1:-1, 2:], P[2:, 2:], P[2:, 1:-1], P[2:, :-2], P[1:-1, :-2], P[:-2, :-2]]


def _crossings(img):
    r = _ring(img)
    return sum(((r[k] == 0) & (r[(k + 1) % 8] == 1)).astype(np.int32) for k in range(8))


def _thin(img):
    """Zhang-Suen: mang 0/1 -> duong tam rong 1 pixel."""
    img = img.astype(np.uint8).copy()
    while True:
        changed = False
        for step in (0, 1):
            p2, p3, p4, p5, p6, p7, p8, p9 = _ring(img)
            b = sum(p.astype(np.int32) for p in (p2, p3, p4, p5, p6, p7, p8, p9))
            if step == 0:
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                c = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            rm = (img == 1) & (b >= 2) & (b <= 6) & (_crossings(img) == 1) & c
            if rm.any():
                img[rm] = 0
                changed = True
        if not changed:
            return img


_N4 = ((-1, 0), (0, 1), (1, 0), (0, -1))
_N8 = _N4 + ((-1, 1), (1, 1), (1, -1), (-1, -1))


def _trace(skel):
    """Duong tam 1 pixel -> cac polyline (y, x) noi giua cac dau mut/nga ba. Tra ve (path, kieu 2 dau)."""
    ys, xs = np.nonzero(skel)
    on = set(zip(ys.tolist(), xs.tolist()))
    cn = _crossings(skel)
    nodes = {p for p in on if cn[p] != 2}
    visited = set()

    def nbrs(p):
        return [(p[0] + dy, p[1] + dx) for dy, dx in _N8 if (p[0] + dy, p[1] + dx) in on]

    def walk(path):
        prev, cur = path[-2], path[-1]
        while cur not in nodes:
            visited.add(cur)
            cand = [q for q in nbrs(cur) if q != prev and q not in visited]
            if not cand:
                break
            prev, cur = cur, cand[0]          # nbrs() xep lan can 4 huong truoc -> di theo net, khong cat goc
            path.append(cur)
        return path

    out = []
    for n in sorted(nodes):
        for q in nbrs(n):
            if q not in nodes and q not in visited:
                p = walk([n, q])
                out.append((p, (int(cn[p[0]]), int(cn[p[-1]]) if p[-1] in nodes else 1)))
    for s in sorted(on - nodes):
        if s in visited:
            continue
        visited.add(s)
        nb = nbrs(s)
        if not nb:
            continue
        p = walk([s, nb[0]])
        if len(p) > 3 and abs(p[-1][0] - s[0]) <= 1 and abs(p[-1][1] - s[1]) <= 1:
            p.append(s)                        # vong kin
        out.append((p, (0, 0)))
    return out


def _chaikin(p, closed, n=2):
    for _ in range(n):
        q = np.roll(p, -1, axis=0) if closed else p[1:]
        a = p if closed else p[:-1]
        mid = np.empty((2 * len(a), 2))
        mid[0::2] = 0.75 * a + 0.25 * q
        mid[1::2] = 0.25 * a + 0.75 * q
        p = mid if closed else np.vstack([p[:1], mid, p[-1:]])
    return p


def _smooth_ring(c, eps=1.0):
    a = cv2.approxPolyDP(c.astype(np.float32).reshape(-1, 1, 2), eps, True)[:, 0, :].astype(float)
    return _chaikin(a, True) if len(a) >= 3 else None


def _mass_boundary(img, mask):
    """Ranh gioi giua cac mang mau/tong khac han nhau ma tranh khong ve net muc: la xanh tren long xam,
    bom long bac tren long den. Chi giu doan ma anh goc doi mau/tong DOT NGOT (vien ve), bo duong
    nguong cat ngang vung to bong mem. Tra ve mang nhi phan rong ~2px, chi nam ben trong chu the."""
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 2), cv2.COLOR_BGR2LAB).astype(np.float32)
    L, a, b = lab[..., 0], lab[..., 1] - 128, lab[..., 2] - 128
    inside = mask > 0
    side = max(mask.shape)
    dc = np.hypot(a - np.median(a[inside]), b - np.median(b[inside]))
    masses = [dc > max(9.0, 2.5 * float(np.median(dc[inside])))]       # khac han mau chu dao cua chu the
    v = L[inside].astype(np.uint8).reshape(-1, 1)
    t, _ = cv2.threshold(v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    lo, hi = L[inside & (L <= t)], L[inside & (L > t)]
    if lo.size and hi.size and hi.mean() - lo.mean() > 3 * np.sqrt(0.5 * (lo.var() + hi.var())):
        masses.append(L > t)                                                          # 2 tong tach ro
    out = np.zeros(mask.shape, np.uint8)
    k3 = np.ones((3, 3), np.uint8)
    for mm in masses:
        mm = (mm & inside).astype(np.uint8)
        mm = cv2.morphologyEx(mm, cv2.MORPH_OPEN, k3)
        mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        _, lab_ids, st, _ = cv2.connectedComponentsWithStats(mm, connectivity=4)
        big = np.r_[False, st[1:, 4] > (side * 0.03) ** 2]
        mm = big[lab_ids].astype(np.uint8)
        out |= cv2.morphologyEx(mm, cv2.MORPH_GRADIENT, k3)
    d = max(3, side // 250)
    out &= cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1,) * 2))
    out &= (cv2.dilate(_lab_gradient(img), np.ones((5, 5), np.uint8)) >= 6).astype(np.uint8)
    _, lab_ids, st, _ = cv2.connectedComponentsWithStats(out, connectivity=8)
    return np.r_[False, st[1:, 4] >= side * 0.04][lab_ids].astype(np.uint8)


def _lab_gradient(img):
    """Do doi mau (Delta E) tren moi pixel, anh lam mo nhe."""
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 1), cv2.COLOR_BGR2LAB).astype(np.float32)
    g2 = np.zeros(lab.shape[:2], np.float32)
    for c in range(3):
        g2 += (cv2.Sobel(lab[..., c], cv2.CV_32F, 1, 0, ksize=3) / 8) ** 2
        g2 += (cv2.Sobel(lab[..., c], cv2.CV_32F, 0, 1, ksize=3) / 8) ** 2
    return np.sqrt(g2)


def detail_art(gray, mask, min_len, cut_border, img=None):
    """Net chi tiet tu anh.
    - Net muc (toi, manh): giu nguyen do day that, vector hoa thanh hinh to den (inks) -> net dam
      khong bi tach thanh 2 duong mep.
    - Canh mau khong co net muc (anh chup): 1 duong tam (lines).
    Tra ve (lines, inks, raster cac net de cat vung, do rong net trung vi tinh bang pixel)."""
    h, w = gray.shape
    g = cv2.bilateralFilter(gray, 9, 60, 9)
    k = max(9, int(round(max(h, w) / 55)) | 1)        # lon hon net dam nhat de bat ca net day
    # net muc = toi hon nen xung quanh: chenh > 40, hoac (anh toi: long gorilla ~50, net ~10) chenh > 18
    # va toi chua bang nua nen. Do sang cua nen = closing; bong mo tren anh sang van khong tinh la net.
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))).astype(np.int32)
    bh = bg - g
    ink = (bh > 40) | ((bh > 18) & (2 * bh > bg))
    ink = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ink &= cv2.dilate(mask, np.ones((5, 5), np.uint8))
    # Canny o sat net muc chi la 2 mep cua chinh net do -> bo, chi giu canh giua 2 mang mau
    v = float(np.median(g[mask > 0]))
    edges = cv2.Canny(g, int(max(0, 0.66 * v)), int(min(255, 1.33 * v)))
    edges[cv2.dilate(ink, np.ones((7, 7), np.uint8)) > 0] = 0
    edges = (cv2.dilate(edges, np.ones((3, 3), np.uint8)) > 0).astype(np.uint8) & mask
    # ranh gioi mang (vien la, bom long bac) ve dam nhu net muc, chi o doan chua co net muc san
    mass = _mass_boundary(img, mask) if img is not None else np.zeros_like(mask)
    band = cv2.dilate(mass, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    ink |= band & (cv2.dilate(ink, np.ones((5, 5), np.uint8)) == 0)
    edges[band > 0] = 0

    # loc theo do dai duong tam cua tung cum net (cum nho = vet ban, long toc vun). Cum co net muc that
    # (soi long ve tay, gan la) duoc giu voi nguong ngan hon nhieu so voi canh Canny thuan.
    m = ink | edges
    skel = _thin(m)
    n, lab = cv2.connectedComponents(m, connectivity=8)
    length = np.bincount(lab[skel > 0], minlength=n)
    has_ink = np.bincount(lab[ink > 0], minlength=n) > 0
    keep = length >= np.where(has_ink, 0.3 * min_len, min_len)
    keep[0] = False
    km = keep[lab]
    ink &= km.astype(np.uint8)
    edges &= km.astype(np.uint8)
    skel &= km.astype(np.uint8)
    width = float(np.clip(2 * np.median(cv2.distanceTransform(m, cv2.DIST_L2, 3)[skel > 0]), 2, 12)) \
        if skel.any() else 3.0

    inks = []
    cnts, hier = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    for i, c in enumerate(cnts):
        if hier[0][i][3] >= 0 or cv2.contourArea(c) < 6:
            continue
        outer = _smooth_ring(c[:, 0, :])
        if outer is None:
            continue
        holes = [_smooth_ring(cnts[j][:, 0, :]) for j in range(len(cnts))
                 if hier[0][j][3] == i and cv2.contourArea(cnts[j]) >= 6]
        inks.append([outer] + [r for r in holes if r is not None])

    # duong tam: cho canh khong muc, va lam do day toi thieu cho net muc rat manh
    inner = cv2.distanceTransform(mask, cv2.DIST_L2, 3) > width / 2 + 2.5 if cut_border else None
    spur = 1.5 * width + 4
    lines = []
    for path, ends in _trace(skel):
        if len(path) < 2:
            continue
        if ends.count(1) == 1 and min(ends) >= 1 and max(ends) >= 3 and len(path) < spur:
            continue                           # rau nho moc ra o nga ba (san pham phu cua lam mong)
        P = np.array(path, float)[:, ::-1]
        runs = [P]
        if inner is not None:                  # vien ngoai chu the da co net silhouette
            ok = inner[np.array(path)[:, 0], np.array(path)[:, 1]]
            cuts = np.flatnonzero(np.diff(np.r_[0, ok.astype(np.int8), 0]))
            runs = [P[a:b] for a, b in zip(cuts[::2], cuts[1::2])]
        for r in runs:
            if len(r) < max(4, spur):
                continue
            closed = len(r) > 8 and np.hypot(*(r[0] - r[-1])) < 1.5
            a = cv2.approxPolyDP(r.astype(np.float32).reshape(-1, 1, 2), 1.2, closed)[:, 0, :].astype(float)
            if len(a) >= 2:
                a = _chaikin(a, closed and len(a) >= 3)
                lines.append(np.vstack([a, a[:1]]) if closed else a)
    lines.sort(key=lambda p: -len(p))

    # vung bi net chiem: mang dung lai dung mep net muc; voi canh khong muc chi cat 1 duong manh
    # ngay tam net (mang 2 ben no 1.2px la gap nhau o tam, khong ho khe trang 2 ben net)
    raster = ink | mass                         # ranh gioi mang luon cat vung (khep kin vien la, bom long)
    for L in lines:
        cv2.polylines(raster, [np.round(L).astype(np.int32)], False, 1, 2)
    return lines, inks, raster, width


# ----------------------------- chia mang -----------------------------
def _parts(g, min_area=4.0):
    """Hinh hoc bat ky -> cac Polygon khong lo thung (fill_poly chi ve vien ngoai)."""
    if g.is_empty:
        return []
    if g.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for x in g.geoms for p in _parts(x, min_area)]
    if g.geom_type != "Polygon" or g.area < min_area:
        return []
    if not g.interiors:
        return [g]
    c = Polygon(g.interiors[0]).representative_point()
    _, miny, _, maxy = g.bounds
    return [p for x in split(g, LineString([(c.x, miny - 1), (c.x, maxy + 1)])).geoms for p in _parts(x, min_area)]


def _contour_geom(region):
    cnts, hier = cv2.findContours(region, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    geoms = []
    for i, c in enumerate(cnts):
        if hier[0][i][3] >= 0 or len(c) < 3:
            continue
        holes = [cnts[j][:, 0, :] for j in range(len(cnts)) if hier[0][j][3] == i and len(cnts[j]) >= 3]
        geoms.append(Polygon(c[:, 0, :], holes).buffer(0))
    return unary_union(geoms) if geoms else Polygon()


def _resample(ring, step):
    p = np.asarray(ring.coords)
    seg = np.hypot(*np.diff(p, axis=0).T)
    t = np.r_[0, np.cumsum(seg)]
    if t[-1] < step:
        return p[:-1]
    s = np.arange(0, t[-1], t[-1] / max(3, round(t[-1] / step)))
    return np.c_[np.interp(s, t, p[:, 0]), np.interp(s, t, p[:, 1])]


def sample_points(gray, free, n_points, rng):
    """Diem ngau nhien trong mang, day hon o cho nhieu chi tiet, cach nhau toi thieu min_d."""
    h, w = gray.shape
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.GaussianBlur(np.hypot(gx, gy), (0, 0), 3)
    min_d = 0.45 * math.sqrt(free.sum() / n_points)
    # khong lay diem sat net/vien: se thanh tam giac mong
    weight = ((edge / (edge.max() + 1e-6)) ** 0.8 + 0.12) * (cv2.distanceTransform(free, cv2.DIST_L2, 3) > 0.5 * min_d)
    prob = (weight / weight.sum()).ravel()
    cell = max(min_d, 1.0)
    grid, pts = {}, []
    for idx in rng.choice(h * w, size=n_points * 6, p=prob):
        y, x = divmod(int(idx), w)
        gi, gj = int(x // cell), int(y // cell)
        if all((px - x) ** 2 + (py - y) ** 2 >= min_d * min_d
               for i in (gi - 1, gi, gi + 1) for j in (gj - 1, gj, gj + 1) for px, py in grid.get((i, j), ())):
            pts.append((float(x), float(y)))
            grid.setdefault((gi, gj), []).append((x, y))
            if len(pts) >= n_points:
                break
    return np.array(pts).reshape(-1, 2), min_d


def _absorb_slivers(cells, region, keys, min_area):
    """Manh vun (tam giac bi vien vung cat cut) -> nhap vao mang ke ben cung vung co canh chung dai nhat."""
    tree = shapely.STRtree(cells)
    root = list(range(len(cells)))
    geom = list(cells)

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    for i in sorted(range(len(cells)), key=lambda k: cells[k].area):
        if cells[i].area >= min_area:
            break
        if find(i) != i or geom[i].area >= min_area:
            continue
        best, best_len = None, 1.0
        for j in tree.query(geom[i].buffer(0.5), predicate="intersects"):
            rj = find(int(j))
            if rj == i or region[rj] != region[i]:
                continue
            shared = geom[i].boundary.intersection(geom[rj].buffer(0.5)).length
            if shared > best_len:
                best, best_len = rj, shared
        if best is None:
            continue
        u = geom[best].union(geom[i]).simplify(0.3)
        if u.geom_type == "Polygon" and not u.interiors:
            geom[best] = u
            root[i] = best
    keep = [i for i in range(len(cells)) if root[i] == i]
    return [geom[i] for i in keep], [region[i] for i in keep], [keys[i] for i in keep]


def build_facets(gray, gray_blur, mask, raster, n_points, merge_ratio, seed, rng, min_cell=0.0):
    """Cat chu the theo net chi tiet thanh tung vung, chia moi vung thanh tam giac.
    Canh mang dung lai o net (nhu mat, mo cua mau tham khao) thay vi cat ngang qua."""
    rnd = random.Random(seed)
    h, w = mask.shape
    free = mask & (1 - raster)
    pts, min_d = sample_points(gray, free, n_points, rng)
    facet_area = 2.2 * min_d * min_d
    mask_geom = _contour_geom(mask).buffer(0.5)
    grow = 1.2                                   # lan nhe vao duoi net de khong ho khe trang

    nreg, lab, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
    plab = lab[pts[:, 1].astype(int), pts[:, 0].astype(int)] if len(pts) else np.zeros(0, int)
    cells, region, tri_edges = [], [], []        # tri_edges: khoa canh tam giac (de gop) cua tung o
    for r in range(1, nreg):
        x, y, bw, bh, area = stats[r]
        if area < max(20, 0.08 * facet_area):
            continue                              # khe nho giua cac net: de trang
        crop = np.pad((lab[y:y + bh, x:x + bw] == r).astype(np.uint8), 1)
        geom = shapely.affinity.translate(_contour_geom(crop), x - 1, y - 1)
        geom = geom.buffer(grow, join_style="mitre", mitre_limit=2).intersection(mask_geom).simplify(0.4)
        ipts = pts[plab == r]
        if area < 2.5 * facet_area:
            for p in _parts(geom):
                cells.append(p); region.append(r); tri_edges.append(())
            continue
        rings = [geom.exterior] + list(geom.interiors) if geom.geom_type == "Polygon" else \
            [rg for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon" for rg in [g.exterior, *g.interiors]]
        P = np.vstack([ipts] + [_resample(rg, 2.6 * min_d) for rg in rings])
        try:
            simplices = Delaunay(P).simplices
        except Exception:
            for p in _parts(geom):
                cells.append(p); region.append(r); tri_edges.append(())
            continue
        shapely.prepare(geom)
        tris = shapely.polygons(P[simplices])
        for s, piece in zip(simplices, shapely.intersection(tris, geom)):
            key = tuple(sorted((r, min(a, b), max(a, b)) for a, b in ((s[0], s[1]), (s[1], s[2]), (s[2], s[0]))))
            for p in _parts(piece):
                cells.append(p); region.append(r); tri_edges.append(key)

    cells, region, tri_edges = _absorb_slivers(cells, region, tri_edges, 0.3 * facet_area)

    # do sang trung binh moi o, khong tinh pixel nam tren net muc
    label = np.full((h, w), -1, np.int32)
    for i, c in enumerate(cells):
        cv2.fillPoly(label, [np.round(np.asarray(c.exterior.coords)).astype(np.int32)], int(i))
    ok = (label >= 0) & (raster == 0)
    sums = np.bincount(label[ok], weights=gray_blur[ok], minlength=len(cells))
    cnts = np.bincount(label[ok], minlength=len(cells))
    allc = np.bincount(label[label >= 0], weights=gray_blur[label >= 0], minlength=len(cells))
    alln = np.bincount(label[label >= 0], minlength=len(cells))
    tones = np.where(cnts > 0, sums / np.maximum(cnts, 1), np.where(alln > 0, allc / np.maximum(alln, 1), 255.0))
    areas = np.array([c.area for c in cells])

    # gop 2 tam giac ke nhau cung vung, cung tong mau thanh tu giac loi
    edge_map = {}
    for i, keys in enumerate(tri_edges):
        for k in keys:
            edge_map.setdefault(k, []).append(i)
    group = list(range(len(cells)))
    used = set()
    pairs = sorted((abs(tones[v[0]] - tones[v[1]]), v[0], v[1]) for v in edge_map.values() if len(v) == 2)
    for diff, i, j in pairs:
        if diff > 18 or i in used or j in used or rnd.random() > merge_ratio:
            continue
        u = cells[i].union(cells[j])
        if u.geom_type == "Polygon" and not u.interiors and u.convex_hull.area - u.area < 0.01 * u.area:
            group[j] = i
            used.update((i, j))
            cells[i] = u.simplify(0.01)
    members_of = {}
    for i in range(len(cells)):
        members_of.setdefault(group[i], []).append(i)
    polys, ftones, fregion, fareas = [], [], [], []
    for i, members in members_of.items():
        a = areas[members]
        ftones.append(float((tones[members] * a).sum() / a.sum()))
        polys.append(np.array(cells[i].exterior.coords)[:-1])
        fregion.append(region[i])
        fareas.append(float(a.sum()))
    if min_cell > 0:
        ys, xs = np.nonzero(mask)
        if len(xs):
            bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            nominal = min(540.0 / bw, 660.0 / bh)         # pt moi pixel xap xi tren trang tranh
            polys, ftones = _merge_small(polys, ftones, fregion, min_cell / nominal, 7.0 * facet_area)

    # mang ke nhau (ke ca hai ben mot net) de chon huong net khac nhau
    geoms = [Polygon(p).buffer(1.0) for p in polys]
    tree = shapely.STRtree(geoms)
    nbrs = [set() for _ in polys]
    for a, b in zip(*tree.query(geoms, predicate="intersects")):
        if a != b:
            nbrs[a].add(int(b))
    return polys, np.array(ftones), nbrs


def _merge_small(polys, tones, region, min_r, max_area):
    """Mang co ban kinh noi tiep < min_r -> gop vao mang ke cung vung co canh chung dai nhat (khong tao lo)."""
    geoms = [Polygon(p).buffer(0) for p in polys]
    tones = list(tones)
    alive = [g.geom_type == "Polygon" and not g.is_empty for g in geoms]

    def inr(g):
        return polylabel(g, tolerance=0.2).distance(g.exterior)

    changed = True
    while changed:
        changed = False
        tree = shapely.STRtree(geoms)
        order = sorted((i for i in range(len(geoms)) if alive[i]), key=lambda k: geoms[k].area)
        for i in order:
            if not alive[i] or geoms[i].is_empty or inr(geoms[i]) >= min_r:
                continue
            best, best_len = None, 0.5
            for j in tree.query(geoms[i].buffer(0.6), predicate="intersects"):
                j = int(j)
                if j == i or not alive[j] or geoms[j].is_empty or region[j] != region[i]:
                    continue
                if geoms[i].area + geoms[j].area > max_area:
                    continue
                shared = geoms[i].boundary.intersection(geoms[j].buffer(0.6)).length
                if shared > best_len:
                    best, best_len = j, shared
            if best is None:
                continue
            u = geoms[i].union(geoms[best]).buffer(0.3, join_style="mitre").buffer(-0.3, join_style="mitre").simplify(0.2)
            if u.is_empty or u.geom_type != "Polygon" or u.interiors:
                continue
            ai, aj = geoms[i].area, geoms[best].area
            tones[best] = (tones[i] * ai + tones[best] * aj) / (ai + aj)
            geoms[best] = u
            alive[i] = False
            changed = True
            tree = shapely.STRtree([g if alive[k] else Polygon() for k, g in enumerate(geoms)])
    keep = [i for i in range(len(geoms)) if alive[i]]
    return [np.array(geoms[i].exterior.coords)[:-1] for i in keep], [tones[i] for i in keep]


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


def _limit_black(polys, tones, levels, nbrs):
    """Mang to den dac chi khi cum mang den lien nhau van nho (mui, con nguoi) -> khong thanh khoi den lon.
    Vung den that (tone < 15) duoc phep cum lon hon, nhung khoi den chiem qua nhieu chu the (bong co, chan den)
    van ha xuong gach cheo: trang to mau khong de mang den lon."""
    idx = np.flatnonzero(levels == 5)
    if not len(idx):
        return
    areas = np.array([Polygon(p).area for p in polys])
    cap = 3 * np.median(areas)
    big = 0.04 * areas.sum()
    cluster = {}                                  # mang den -> id cum; dien tich tung cum
    size = {}
    for i in sorted(idx, key=lambda i: tones[i]):
        near = {cluster[j] for j in nbrs[i] if j in cluster}
        total = areas[i] + sum(size[c] for c in near)
        if total > (big if tones[i] < 15 else cap):
            levels[i] = 4
            continue
        cid = int(i)
        for c in near:                            # gop cac cum ke vao cum moi
            for j in [k for k, v in cluster.items() if v == c]:
                cluster[j] = cid
            size.pop(c)
        cluster[int(i)] = cid
        size[cid] = total


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


def dark_accents(gray_blur, mask, line_w=3.0, thick=None):
    """Mang den dac (con nguoi, mui). Mo bang nhan lon hon be rong net de net muc khong bi to thanh mang."""
    inside = gray_blur[mask > 0]
    thr = min(45.0, float(np.percentile(inside, 2.5)))
    b = ((gray_blur <= thr) & (mask > 0)).astype(np.uint8)
    if thick is not None:
        b &= 1 - thick
    k = max(3, int(round(1.6 * line_w)) | 1)
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    cnts, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    total = mask.sum()
    out = []
    for c in cnts:
        if 25 < cv2.contourArea(c) < 0.015 * total:
            c = cv2.approxPolyDP(c, 1.2, True)
            if len(c) >= 3:
                out.append(_chaikin(c[:, 0, :].astype(float), True))
    return out


THICK_DARK = 0.022     # khoi den day hon ~4.5% canh lon chu the thi khong to den dac (trang to mau can cho de to)
PURE_BLACK = 12        # khoi day ma den tuyet doi (max kenh mau <= nay) la chu y thiet ke (chan den...) -> giu den


def thick_dark(dark, mask, img=None):
    """Phan 'day' cua vung den (vua mot hinh tron duong kinh ~4.5% chu the): bong co, chan den, vien canh den rong.
    Trang to mau ma co khoi den lon thi khong con gi de to va nhin nang ne -> phan nay de mang gach cheo (muc 4).
    Phan mong (soc van, dom, vien canh hep, mieng, con nguoi) van giu den."""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return np.zeros_like(dark)
    r = int(THICK_DARK * max(xs.max() - xs.min(), ys.max() - ys.min()))
    if r < 4:
        return np.zeros_like(dark)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    thick = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_OPEN, k)
    if img is not None:
        # chi bo to den cho khoi mau SAM (bong, mieng do sam, long nau sam); khoi den tuyet doi giu nhu anh goc
        v = img.max(axis=2) if img.ndim == 3 else img
        n, lab = cv2.connectedComponents(thick)
        for i in range(1, n):
            sel = lab == i
            if np.median(v[sel]) <= PURE_BLACK:
                thick[sel] = 0
    return thick


def solid_dark(raw, mask, line_w=3.0, thick=None):
    """Vung den dac that cua anh goc (chan, tai, long): to den nguyen khoi theo pixel goc,
    khong bi net muc / mang bo sot hoac khoet thanh lo trang. Net muc manh (mong) khong tinh vi da co lop net."""
    g = cv2.GaussianBlur(raw, (0, 0), 1.2)
    d = ((g <= 55) & (mask > 0)).astype(np.uint8)
    if thick is not None:
        d &= 1 - thick                      # khoi den day (co, chan, canh den) -> de mang gach cheo, khong to den
    k = max(5, int(round(2.2 * line_w)) | 1)
    core = cv2.morphologyEx(d, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    if not core.any():
        return []
    # nong lai trong vung toi de lay du mep, roi lap lo nho
    grown = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) & d
    grown = cv2.morphologyEx(grown, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    grown = _fill_small_holes(grown, 0.0006 * mask.sum())  # lap lo nho (vet sang); lo lon (luoi, rang trong mieng) giu nguyen
    if thick is not None:
        grown &= 1 - thick                                # ...nhung khong lap lai cho khoi den day vua khoet ra
    cnts, hier = cv2.findContours(grown, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for i, (c, hh) in enumerate(zip(cnts, hier[0])):
        if hh[3] != -1 or cv2.contourArea(c) < 60:
            continue
        holes = [cnts[j][:, 0, :] for j in range(len(cnts)) if hier[0][j][3] == i and len(cnts[j]) >= 3]
        if not holes:
            c = cv2.approxPolyDP(c, 1.0, True)
            if len(c) >= 3:
                out.append(_chaikin(c[:, 0, :].astype(float), True))
            continue
        # vien den bao quanh khoi da khoet: cat thanh cac manh khong lo (lop accents chi ve vien ngoai)
        for part in _parts(Polygon(c[:, 0, :], holes).buffer(0), 60):
            a = np.asarray(part.simplify(1.0).exterior.coords)[:-1]
            if len(a) >= 3:
                out.append(_chaikin(a, True))
    return out


def _fill_holes(m):
    inv = np.pad(1 - m, 1, constant_values=1).astype(np.uint8)
    cv2.floodFill(inv, None, (0, 0), 2)
    return (inv[1:-1, 1:-1] != 2).astype(np.uint8)


def _fill_small_holes(m, max_area):
    """Chi lap cac lo kin nho hon max_area (vet sang trong vung den); lo lon (luoi/rang/mat trong mieng den) de nguyen."""
    holes = _fill_holes(m) & (1 - m)
    n, lab, st, _ = cv2.connectedComponentsWithStats(holes, connectivity=4)
    out = m.copy()
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] <= max_area:
            out[lab == i] = 1
    return out


def _snap_to_ink(mask, ink):
    """Mep mask (tach nen theo mau) nam ngoai net vien muc vai pixel (vien mo cua net).
    Got bo vien do de duong silhouette trung voi mep ngoai net muc, khong de lai 1 dai mang hep
    giua hai net (nhin nhu net vien bi tach doi)."""
    h, w = mask.shape
    d = max(3, int(round(max(h, w) / 250)))
    core = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1)))
    m = mask & (core | cv2.dilate(ink, np.ones((3, 3), np.uint8)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
    if n > 1:
        m = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    return m if m.sum() > 0.5 * mask.sum() else mask


def make_design(image_bytes: bytes, params: EngineParams) -> Design:
    img, alpha = decode_image(image_bytes)
    raw = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(raw)
    mask = subject_mask(img, alpha, params.grabcut)
    gray_blur = cv2.GaussianBlur(gray, (0, 0), 2).astype(np.float64)
    rng = np.random.default_rng(params.seed)
    full = bool(mask.all())

    if params.lineart > 0:
        lines, inks, raster, line_w = detail_art(raw, mask, params.lineart * math.sqrt(mask.sum()), not full, img)
    else:
        lines, inks, raster, line_w = [], [], np.zeros_like(mask), 3.0
    keeps = []
    if params.accents:                      # tu dong giu nguyen mat; nguoi dung bot/them trong che do sua
        for k, ring in enumerate(_merge_rings([c for _, _, c in find_eyes(img, mask)], 3.0)):
            keeps.append({"id": f"e{k}", **keep_art(raw, ring)})
    if not full and inks:
        mask = _snap_to_ink(mask, raster)
    polys, tones, nbrs = build_facets(gray, gray_blur, mask, raster, max(params.facets, 30),
                                      params.merge, params.seed, rng, params.min_cell)
    levels = assign_levels(tones, params.white, params.black)
    _limit_black(polys, tones, levels, nbrs)
    angles = assign_angles(polys, levels, nbrs, params.min_angle_gap)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    sil = []
    for c in cnts:
        if cv2.contourArea(c) > 100:
            s = cv2.approxPolyDP(c, 1.0, True)[:, 0, :].astype(float)
            sil.append(s if full else _chaikin(s, True, 1))

    accents = []
    if params.accents:
        dk = ((cv2.GaussianBlur(raw, (0, 0), 1.2) <= 55) & (mask > 0)).astype(np.uint8)
        # no them de khong sot vien vun den quanh khoi den day
        thick = cv2.dilate(thick_dark(dk, mask, img), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
        accents = dark_accents(gray_blur, mask, line_w, thick) + solid_dark(raw, mask, line_w, thick)

    h, w = gray.shape
    stats = {
        "facets": len(polys),
        "levels": {str(lv): int((levels == lv).sum()) for lv in range(6)},
        "image_px": [w, h],
    }
    stats["keeps"] = len(keeps)
    return Design(w, h, polys, [int(x) for x in levels], angles, sil, accents, lines, stats,
                  inks=inks, keeps=keeps, gray=raw)


def _merge_rings(rings, grow):
    """Gop cac vung chong nhau (2 diem sang trong cung 1 mat), no them 'grow' px de lay ca vien mong mat."""
    geoms = [Polygon(r).buffer(grow) for r in rings if len(r) >= 3]
    u = unary_union(geoms) if geoms else Polygon()
    parts = list(getattr(u, "geoms", [u])) if not u.is_empty else []
    return [np.array(p.exterior.coords)[:-1] for p in parts if p.geom_type == "Polygon"]
