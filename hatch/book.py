"""
Ghep ruot sach.

Thu tu: trang ten sach (p1) -> ban quyen (p2, mat sau trang ten) -> huong dan -> khoi dong -> cac tranh -> dap an.
Trang huong dan, khoi dong va moi tranh deu nam o trang phai (trang le) va co trang trang phia sau
(neu bat blank_back) de in mot mat. Tong so trang lam tron chan, toi thieu 24 trang (KDP).
Cung mot ham draw_page dung cho ca PDF va anh xem truoc SVG, nen xem truoc dung voi file xuat.
"""
from . import pages as P
from .layout import page_geometry, min_gutter_in
from .render import StyleParams, SvgBackend, design_page, overlay_guides, render_pdf

KDP_MIN_PAGES = 24


def plan_pages(proj):
    s = proj["settings"]
    n = len(proj["designs"])
    blank_back = bool(s["blank_back"])
    seq = []

    def add_right(page, back=blank_back):
        if len(seq) % 2 == 1:
            seq.append({"kind": "blank"})
        seq.append(page)
        if back:
            seq.append({"kind": "blank"})

    if s["title_page"]:
        add_right({"kind": "title"}, back=False)
    if s["copyright_page"]:
        if len(seq) % 2 == 0 and seq:       # chi xay ra khi khong co trang ten
            seq.append({"kind": "blank"})
        seq.append({"kind": "copyright"})
    if s["howto_page"]:
        add_right({"kind": "howto"})
    if s["warmup_page"]:
        add_right({"kind": "warmup"})
    for i in range(n):
        if blank_back:
            add_right({"kind": "design", "i": i})
        else:
            seq.append({"kind": "design", "i": i})
    if s["include_keys"] and n:
        per = max(1, min(4, int(s["keys_per_page"])))
        if len(seq) % 2 == 1:
            seq.append({"kind": "blank"})
        for k in range(0, n, per):
            seq.append({"kind": "keys", "items": list(range(k, min(n, k + per))), "first": k == 0})
    if len(seq) % 2 == 1:
        seq.append({"kind": "blank"})
    if s["pad_to_min"]:
        while len(seq) < KDP_MIN_PAGES:
            seq.append({"kind": "blank"})
    for no, pg in enumerate(seq, start=1):
        pg["n"] = no
        pg["side"] = "right" if no % 2 == 1 else "left"
    return seq


def geometry_for(proj, side, total):
    s = proj["settings"]
    return page_geometry(bool(s["bleed"]), side, max(total, KDP_MIN_PAGES),
                         float(s["padding_in"]), float(s["extra_margin_in"]))


def page_drawer(proj, seq, pg, resolve):
    """Tra ve (geom, fn(be)) cho 1 trang. resolve(i) -> Design da ap chinh sua."""
    total = len(seq)
    geom = geometry_for(proj, pg["side"], total)
    style = StyleParams.from_dict(proj["style"])
    num = pg["n"] if proj["settings"]["page_numbers"] else None
    kind = pg["kind"]
    design_page_no = {p["i"]: p["n"] for p in seq if p["kind"] == "design"}

    if kind == "blank":
        fn = lambda be: None
    elif kind == "title":
        fn = lambda be: P.title_page(be, geom, proj, style)
    elif kind == "copyright":
        fn = lambda be: P.copyright_page(be, geom, proj, style, num)
    elif kind == "howto":
        fn = lambda be: P.howto_page(be, geom, proj, style, num, proj["settings"]["include_keys"])
    elif kind == "warmup":
        fn = lambda be: P.warmup_page(be, geom, proj, style, num)
    elif kind == "design":
        item = proj["designs"][pg["i"]]
        fn = lambda be: design_page(be, resolve(pg["i"]), geom, "page", style, bool(item.get("frame")), num)
    elif kind == "keys":
        entries = [(resolve(i), i + 1, design_page_no.get(i) if proj["settings"]["page_numbers"] else None)
                   for i in pg["items"]]
        fn = lambda be: P.keys_page(be, geom, entries, style, num, pg.get("first"))
    else:
        raise ValueError(f"Loai trang khong ro: {kind}")
    return geom, fn


def build_book(proj, resolve):
    seq = plan_pages(proj)
    draws = []
    for pg in seq:
        geom, fn = page_drawer(proj, seq, pg, resolve)
        draws.append((geom.page_w, geom.page_h, fn))
    pdf = render_pdf(draws, title=proj["title"] or "Coloring Book", author=proj["author"])
    g = geometry_for(proj, "right", len(seq))
    info = {
        "total_pages": len(seq),
        "gutter_in": round(g.gutter_in, 4),
        "bleed": g.bleed,
        "page_size_in": [round(g.page_w / 72, 3), round(g.page_h / 72, 3)],
    }
    return pdf, info


def page_svg(proj, n, resolve, show_guides=False):
    seq = plan_pages(proj)
    pg = seq[n - 1]
    geom, fn = page_drawer(proj, seq, pg, resolve)
    be = SvgBackend(geom.page_w, geom.page_h)
    fn(be)
    if show_guides:
        overlay_guides(be, geom)
    return be.result()


def summary(proj):
    seq = plan_pages(proj)
    total = len(seq)
    g = geometry_for(proj, "right", total)
    return {
        "total_pages": total,
        "gutter_in": round(g.gutter_in, 4),
        "min_gutter_in": min_gutter_in(total),
        "outside_in": round(g.outside_in, 4),
        "page_size_in": [round(g.page_w / 72, 3), round(g.page_h / 72, 3)],
        "pages": [{k: v for k, v in p.items()} for p in seq],
    }
