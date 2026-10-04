"""
Chinh sua tay tren mot thiet ke da sinh: doi muc sang toi, doi huong net, gop 2 mang, tach 1 mang.

Chinh sua luu thanh danh sach thao tac, ap dung lan luot len ban goc (ban goc nam trong cache):
  {"op": "level", "id": "f12", "v": 3}
  {"op": "angle", "id": "f12", "v": 45}
  {"op": "merge", "a": "f12", "b": "f40"}     # f40 nhap vao f12, giu muc + huong cua f12
  {"op": "split", "id": "f12"}                 # -> "f12a", "f12b"
Id chi on dinh khi tham so engine giu nguyen; doi tham so engine thi phai xoa chinh sua.
"""
import math
import warnings

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import split, unary_union

from .engine import Design


def _poly(p):
    g = Polygon(p)
    return g if g.is_valid else g.buffer(0)


def _merge(pa, pb):
    a, b = _poly(pa), _poly(pb)
    if a.geom_type != "Polygon" or b.geom_type != "Polygon":
        return None
    if a.intersection(b).length < 1.0:          # phai chung mot canh, khong chi cham dinh
        return None
    u = unary_union([a, b]).simplify(0.05)
    if u.geom_type != "Polygon" or len(u.interiors):
        return None
    return np.array(u.exterior.coords)[:-1]


def _split(p):
    g = _poly(p)
    if g.geom_type != "Polygon" or g.area < 20:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mrr = g.minimum_rotated_rectangle
    rect = np.array(mrr.exterior.coords)[:4]
    e1, e2 = rect[1] - rect[0], rect[2] - rect[1]
    axis = e1 if np.hypot(*e1) >= np.hypot(*e2) else e2      # truc dai
    axis = axis / (np.hypot(*axis) + 1e-9)
    c = np.array(g.centroid.coords[0])
    n = np.array([-axis[1], axis[0]])                         # cat vuong goc truc dai
    R = 2 * math.hypot(*(rect[2] - rect[0]))
    parts = split(g, LineString([c - n * R, c + n * R]))
    geoms = [x for x in parts.geoms if x.geom_type == "Polygon" and x.area > 1]
    if len(geoms) != 2:
        return None
    return [np.array(x.exterior.coords)[:-1] for x in geoms]


def apply_edits(design: Design, edits) -> Design:
    if not edits:
        return design
    ids = list(design.ids)
    polys = [np.asarray(p, float) for p in design.polys]
    levels = list(design.levels)
    angles = list(design.angles)
    skipped = 0

    def at(k):
        try:
            return ids.index(k)
        except ValueError:
            return -1

    for e in edits:
        op = e.get("op")
        if op in ("level", "angle"):
            i = at(e.get("id"))
            if i < 0:
                skipped += 1
                continue
            if op == "level":
                levels[i] = int(min(max(int(e.get("v", 0)), 0), 5))
            else:
                angles[i] = float(e.get("v", 0)) % 180
        elif op == "merge":
            i, j = at(e.get("a")), at(e.get("b"))
            merged = _merge(polys[i], polys[j]) if i >= 0 and j >= 0 and i != j else None
            if merged is None:
                skipped += 1
                continue
            polys[i] = merged
            for lst in (ids, polys, levels, angles):
                del lst[j]
        elif op == "split":
            i = at(e.get("id"))
            parts = _split(polys[i]) if i >= 0 else None
            if parts is None:
                skipped += 1
                continue
            base = ids[i]
            ids[i:i + 1] = [base + "a", base + "b"]
            polys[i:i + 1] = parts
            levels[i:i + 1] = [levels[i], levels[i]]
            angles[i:i + 1] = [angles[i], (angles[i] + 60) % 180]
        else:
            skipped += 1

    lv = np.array(levels)
    stats = dict(design.stats)
    stats.update(facets=len(polys), levels={str(k): int((lv == k).sum()) for k in range(6)},
                 edits=len(edits), edits_skipped=skipped)
    return Design(design.width, design.height, polys, levels, angles, design.silhouette,
                  design.accents, design.lines, stats, ids)
