"""
File bia KDP (bia sau + gay + bia truoc trong 1 trang PDF).

  Do day gay = so trang x do day giay (trang: 0.002252 in/trang, kem: 0.0025 in/trang)
  Rong = 0.125 + 8.5 + gay + 8.5 + 0.125     Cao = 0.125 + 11 + 0.125
Chu tren gay chi duoc phep khi sach > 79 trang, va phai cach mep gay >= 0.0625 in.
Chu tren bia giu cach mep cat >= 0.125 in; o day dung 0.375 in cho an toan.
Vung ma vach: KDP tu dat ma vach 2 x 1.2 in o goc duoi phai bia sau, tool de trong vung do.
Hay doi chieu voi cong cu Cover Calculator cua KDP truoc khi nop.
"""
from . import fonts
from .layout import Box, PT, TRIM_W_IN, TRIM_H_IN
from .render import StyleParams, SvgBackend, draw_design, render_pdf

BLEED = 0.125
PAPER = {"white": 0.002252, "cream": 0.0025}
SPINE_TEXT_MIN_PAGES = 80
SAFE = 0.375


def cover_geometry(page_count, paper="white"):
    spine = page_count * PAPER.get(paper, PAPER["white"])
    w = 2 * BLEED + 2 * TRIM_W_IN + spine
    h = 2 * BLEED + TRIM_H_IN
    back = Box(BLEED * PT, BLEED * PT, TRIM_W_IN * PT, TRIM_H_IN * PT)
    sp = Box(back.x2, back.y, spine * PT, back.h)
    front = Box(sp.x2, back.y, TRIM_W_IN * PT, back.h)
    return {
        "w": w * PT, "h": h * PT, "back": back, "spine": sp, "front": front,
        "spine_in": round(spine, 4), "size_in": [round(w, 4), round(h, 4)],
        "spine_text": page_count >= SPINE_TEXT_MIN_PAGES,
    }


def _inset(b, d):
    return Box(b.x + d, b.y + d, b.w - 2 * d, b.h - 2 * d)


def draw_cover(be, proj, cg, design, page_count, guides=False):
    cov = proj["cover"]
    dark = cov.get("theme") == "dark"
    ink, paper = (1.0, 0.0) if dark else (0.0, 1.0)
    style = StyleParams.from_dict(proj["style"])
    be.rect(0, 0, cg["w"], cg["h"], fill=paper)

    # ----- bia truoc -----
    fs = _inset(cg["front"], SAFE * PT)
    y = fs.y + 10
    for line in fonts.wrap(proj["title"] or "Untitled", 40, fs.w, "bold"):
        y += 46
        be.text(fs.x + fs.w / 2, y, line, 40, ink, "bold")
    if proj["subtitle"]:
        y += 6
        for line in fonts.wrap(proj["subtitle"], 17, fs.w - 40):
            y += 24
            be.text(fs.x + fs.w / 2, y, line, 17, 0.75 if dark else 0.25)
    bottom = fs.y2 - (40 if proj["author"] else 10)
    art = Box(fs.x, y + 28, fs.w, bottom - y - 50)
    if design is not None:
        if dark:
            be.rect(art.x - 10, art.y - 10, art.w + 20, art.h + 20, fill=1.0, r=12)
        draw_design(be, design, art, cov.get("front_mode", "key"), style)
    if proj["author"]:
        be.text(fs.x + fs.w / 2, fs.y2 - 8, proj["author"], 18, ink)

    # ----- gay -----
    sp = cg["spine"]
    if cg["spine_text"] and proj["title"]:
        room = sp.w - 2 * 0.0625 * PT
        size = max(6.0, min(14.0, room * 0.72))
        text = proj["title"] + (f"   ·   {proj['author']}" if proj["author"] else "")
        be.text(sp.x + sp.w / 2 - size * 0.35, sp.y + sp.h / 2, text, size, ink, "bold", "middle", rotate=90)

    # ----- bia sau -----
    bs = _inset(cg["back"], SAFE * PT)
    if proj["back_text"]:
        y = bs.y + 20
        for line in fonts.wrap(proj["back_text"], 12.5, bs.w * 0.82):
            y += 19
            be.text(bs.x + 0.09 * bs.w, y, line, 12.5, ink, "regular", "start")

    if guides:
        cover_guides(be, cg)


def barcode_box(cg):
    b = cg["back"]
    w, h = 2.0 * PT, 1.2 * PT
    return Box(b.x2 - 0.25 * PT - w, b.y2 - 0.25 * PT - h, w, h)


def cover_guides(be, cg):
    be.raw('<g pointer-events="none">')
    for bx in (cg["back"], cg["front"]):
        be.raw(f'<rect x="{bx.x}" y="{bx.y}" width="{bx.w}" height="{bx.h}" fill="none" stroke="#e0484d" stroke-width="1"/>')
        s = _inset(bx, SAFE * PT)
        be.raw(f'<rect x="{s.x}" y="{s.y}" width="{s.w}" height="{s.h}" fill="none" stroke="#1f8fc4" '
               f'stroke-width="0.8" stroke-dasharray="4 3"/>')
    sp = cg["spine"]
    be.raw(f'<rect x="{sp.x}" y="{sp.y}" width="{sp.w}" height="{sp.h}" fill="#7a5cc7" fill-opacity="0.12" '
           f'stroke="#7a5cc7" stroke-width="1"/>')
    bc = barcode_box(cg)
    be.raw(f'<rect x="{bc.x}" y="{bc.y}" width="{bc.w}" height="{bc.h}" fill="#fff" stroke="#e6a23a" '
           f'stroke-width="1.2" stroke-dasharray="5 3"/>')
    be.raw(f'<text x="{bc.x + bc.w / 2}" y="{bc.y + bc.h / 2 + 4}" font-size="11" text-anchor="middle" '
           f'fill="#b77a14" font-family="Lato, sans-serif">Barcode area</text>')
    be.raw("</g>")


def cover_svg(proj, design, page_count, guides=True):
    cg = cover_geometry(page_count, proj["cover"].get("paper", "white"))
    be = SvgBackend(cg["w"], cg["h"])
    draw_cover(be, proj, cg, design, page_count, guides)
    return be.result(), cg


def cover_pdf(proj, design, page_count):
    cg = cover_geometry(page_count, proj["cover"].get("paper", "white"))
    pdf = render_pdf([(cg["w"], cg["h"], lambda be: draw_cover(be, proj, cg, design, page_count))],
                     title=(proj["title"] or "Cover") + " - cover", author=proj["author"])
    return pdf, cg
