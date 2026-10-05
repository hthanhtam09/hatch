"""Chay: ./.venv/bin/python -m unittest discover tests"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hatch import book as B                         # noqa: E402
from hatch.cover import cover_geometry              # noqa: E402
from hatch.edits import apply_edits                 # noqa: E402
from hatch.engine import EngineParams, make_design  # noqa: E402
from hatch.layout import min_gutter_in              # noqa: E402
from hatch.project import normalize                 # noqa: E402

with open(os.path.join(ROOT, "samples", "cat.jpg"), "rb") as f:
    CAT = f.read()
DESIGN = make_design(CAT, EngineParams())


class EngineTest(unittest.TestCase):
    def test_design(self):
        self.assertGreater(len(DESIGN.polys), 100)
        self.assertEqual(len(DESIGN.ids), len(DESIGN.polys))
        self.assertTrue(all(0 <= lv <= 5 for lv in DESIGN.levels))

    def test_edits(self):
        a, b = DESIGN.ids[:2]
        d = apply_edits(DESIGN, [{"op": "level", "id": a, "v": 5}, {"op": "angle", "id": b, "v": 200},
                                 {"op": "split", "id": a}, {"op": "missing"}])
        self.assertEqual(len(d.polys), len(DESIGN.polys) + 1)
        self.assertEqual(d.levels[d.ids.index(a + "a")], 5)
        self.assertEqual(d.angles[d.ids.index(b)], 20.0)
        self.assertEqual(d.stats["edits_skipped"], 1)
        self.assertEqual(len(DESIGN.polys), len(DESIGN.ids))   # ban goc trong cache khong bi doi

    def test_merge_adjacent(self):
        from shapely.geometry import Polygon
        P = [Polygon(p) for p in DESIGN.polys]
        j = next(j for j in range(1, len(P)) if P[0].intersection(P[j]).length > 1)
        d = apply_edits(DESIGN, [{"op": "merge", "a": DESIGN.ids[0], "b": DESIGN.ids[j]}])
        self.assertEqual(len(d.polys), len(DESIGN.polys) - 1)
        self.assertEqual(d.stats["edits_skipped"], 0)


class KeepTest(unittest.TestCase):
    def test_keep_add_del(self):
        n = len(DESIGN.keeps)
        d = apply_edits(DESIGN, [{"op": "keep_add", "x": 200, "y": 150, "r": 25},
                                 {"op": "keep_add", "x": -5, "y": 10, "r": 25},      # ngoai anh -> bo qua
                                 {"op": "keep_del", "id": "m0"}, {"op": "keep_del", "id": "zz"}])
        self.assertEqual(len(d.keeps), n)
        self.assertEqual(d.stats["edits_skipped"], 2)
        d = apply_edits(DESIGN, [{"op": "keep_add", "x": 200, "y": 150, "r": 25}])
        kp = d.keeps[-1]
        self.assertEqual(kp["id"], "m0")
        self.assertTrue(kp["black"] or kp["dense"] or kp["sparse"])
        self.assertEqual(len(DESIGN.keeps), n)                                     # ban goc khong bi doi

    def test_keep_svg(self):
        from hatch.layout import page_geometry
        from hatch.render import StyleParams, render_svg
        d = apply_edits(DESIGN, [{"op": "keep_add", "x": 200, "y": 150, "r": 25}])
        svg = render_svg(d, page_geometry(True, "right", 100), "color", StyleParams(), interactive=True)
        self.assertIn('id="keeps"', svg)
        self.assertIn('data-keep="m0"', svg)
        self.assertIn('class="artmap"', svg)


class BookTest(unittest.TestCase):
    def proj(self, n=3, **settings):
        return normalize({"title": "T", "designs": [{"image_id": "x"}] * n, "settings": settings})

    def test_designs_on_right_pages(self):
        seq = B.plan_pages(self.proj(5, include_keys=True))
        self.assertEqual(len(seq) % 2, 0)
        self.assertGreaterEqual(len(seq), 24)
        for p in seq:
            if p["kind"] in ("design", "howto", "warmup", "title"):
                self.assertEqual(p["side"], "right")
                self.assertEqual(seq[p["n"]]["kind"] if p["kind"] != "title" else "blank", "blank")
        self.assertEqual(seq[1]["kind"], "copyright")

    def test_no_padding(self):
        seq = B.plan_pages(self.proj(1, pad_to_min=False, title_page=False, copyright_page=False,
                                     howto_page=False, warmup_page=False))
        self.assertEqual([p["kind"] for p in seq], ["design", "blank"])

    def test_gutter(self):
        self.assertEqual(min_gutter_in(24), 0.375)
        self.assertEqual(min_gutter_in(151), 0.5)
        self.assertEqual(min_gutter_in(828), 0.875)

    def test_pdf_fonts_embedded(self):
        proj = self.proj(1, include_keys=True)
        pdf, info = B.build_book(proj, lambda i: DESIGN)
        self.assertEqual(info["page_size_in"], [8.625, 11.25])
        self.assertNotIn(b"/Helvetica", pdf)                      # chi dung font nhung


class CoverTest(unittest.TestCase):
    def test_size(self):
        cg = cover_geometry(100)
        self.assertAlmostEqual(cg["spine_in"], 0.2252, places=4)
        self.assertAlmostEqual(cg["size_in"][0], 17.25 + 0.2252, places=3)
        self.assertEqual(cg["size_in"][1], 11.25)
        self.assertTrue(cg["spine_text"])
        self.assertFalse(cover_geometry(78)["spine_text"])


if __name__ == "__main__":
    unittest.main()
