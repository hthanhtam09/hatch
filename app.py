"""
Hatch Studio - giao dien web chay tren may de tao sach to kieu low-poly + ky hieu gach net cho KDP.

Chay:  pnpm run dev  (Flask API o cong 5050 + giao dien Next.js o cong 3000)
"""
import hashlib
import io
import json
import os
import threading
import time
from collections import OrderedDict

from flask import Flask, jsonify, redirect, request, send_file, send_from_directory

from hatch import book as B
from hatch.cover import cover_pdf, cover_svg
from hatch.edits import apply_edits
from hatch.engine import EngineParams, make_design
from hatch.project import normalize
from hatch.render import StyleParams, render_pdf, render_svg, design_page

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE, "data", "uploads")
EXPORTS = os.path.join(BASE, "data", "exports")
PROJECT = os.path.join(BASE, "data", "project.json")
FONTS = os.path.join(BASE, "hatch", "fonts")
os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(EXPORTS, exist_ok=True)

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024

_cache = OrderedDict()
_lock = threading.Lock()
CACHE_SIZE = 64


def load_image(image_id):
    path = os.path.join(UPLOADS, os.path.basename(image_id))
    if not os.path.exists(path):
        raise FileNotFoundError("Không tìm thấy ảnh gốc, hãy tải lên lại.")
    with open(path, "rb") as f:
        return f.read()


def base_design(image_id, params: EngineParams):
    key = (image_id, params)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    design = make_design(load_image(image_id), params)
    with _lock:
        _cache[key] = design
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return design


def item_design(item):
    d = base_design(item["image_id"], EngineParams.from_dict(item.get("engine") or {}))
    return apply_edits(d, item.get("edits") or [])


def resolver(proj):
    memo = {}

    def resolve(i):
        if i not in memo:
            memo[i] = item_design(proj["designs"][i])
        return memo[i]
    return resolve


def safe_name(s, fallback):
    s = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (s or "").strip())[:60]
    return s or fallback


def pdf_response(data, name):
    with open(os.path.join(EXPORTS, name), "wb") as f:
        f.write(data)
    return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True, download_name=name)


@app.errorhandler(Exception)
def on_error(e):
    code = getattr(e, "code", 500)
    if not isinstance(code, int):
        code = 500
    if code == 500:
        app.logger.exception(e)
    return jsonify(error=str(e)), code


@app.get("/")
def index():
    # Giao dien chinh la Next.js (thu muc web/). Flask chi con lam API.
    return redirect(os.environ.get("HATCH_WEB", "http://127.0.0.1:3000"))


@app.get("/legacy")
def legacy():
    """Giao dien HTML cu, giu lai de du phong."""
    return send_from_directory(app.static_folder, "index.html")


@app.get("/fonts/<path:name>")
def font_file(name):
    return send_from_directory(FONTS, name)


# ----------------------------- du an -----------------------------
@app.get("/api/project")
def project_get():
    if os.path.exists(PROJECT):
        with open(PROJECT, encoding="utf-8") as f:
            return jsonify(normalize(json.load(f)))
    return jsonify(normalize({}))


@app.post("/api/project")
def project_save():
    proj = normalize(request.get_json(force=True))
    tmp = PROJECT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(proj, f, ensure_ascii=False)
    os.replace(tmp, PROJECT)
    return jsonify(ok=True, saved_at=time.strftime("%H:%M:%S"))


@app.post("/api/upload")
def upload():
    f = request.files.get("image")
    if not f:
        return jsonify(error="Chưa chọn ảnh."), 400
    data = f.read()
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        return jsonify(error="Chỉ nhận PNG, JPG hoặc WEBP."), 400
    image_id = hashlib.sha1(data).hexdigest()[:16] + ext
    with open(os.path.join(UPLOADS, image_id), "wb") as out:
        out.write(data)
    return jsonify(image_id=image_id, name=f.filename)


# ----------------------------- 1 tranh -----------------------------
def design_context(d):
    """Tranh dang sua + du an (de lay style, le, so trang, vi tri trang)."""
    proj = normalize(d.get("project"))
    item = d["item"]
    seq = B.plan_pages(proj) if proj["designs"] else []
    total = max(len(seq), B.KDP_MIN_PAGES)
    idx = d.get("index")
    page = next((p for p in seq if p["kind"] == "design" and p.get("i") == idx), None)
    side = page["side"] if page else "right"
    num = page["n"] if page and proj["settings"]["page_numbers"] else None
    geom = B.geometry_for(proj, side, total)
    return proj, item, geom, StyleParams.from_dict(proj["style"]), num


@app.post("/api/render")
def render():
    d = request.get_json(force=True)
    t0 = time.time()
    proj, item, geom, style, num = design_context(d)
    design = item_design(item)
    show = bool(d.get("show_guides", True))
    frame = bool(item.get("frame"))
    views = d.get("views", ["page", "key"])
    out = {v + "_svg": render_svg(design, geom, v, style, show, frame, interactive=bool(d.get("interactive")),
                                  page_no=num) for v in views}
    out.update(stats=design.stats, geometry=geom.info(), ms=int((time.time() - t0) * 1000))
    return jsonify(out)


@app.post("/api/export/design")
def export_design():
    d = request.get_json(force=True)
    proj, item, geom, style, num = design_context(d)
    design = item_design(item)
    mode, fmt = d.get("mode", "page"), d.get("format", "pdf")
    name = f"{safe_name(os.path.splitext(item.get('name') or '')[0], 'design')}_{mode}"
    if fmt == "svg":
        svg = render_svg(design, geom, mode, style, False, bool(item.get("frame")), page_no=num, physical=True)
        return send_file(io.BytesIO(svg.encode()), mimetype="image/svg+xml", as_attachment=True,
                         download_name=name + ".svg")
    data = render_pdf([(geom.page_w, geom.page_h,
                        lambda be: design_page(be, design, geom, mode, style, bool(item.get("frame")), num))],
                      title=name)
    return pdf_response(data, name + ".pdf")


# ----------------------------- sach -----------------------------
@app.post("/api/book/plan")
def book_plan():
    return jsonify(B.summary(normalize(request.get_json(force=True))))


@app.post("/api/book/page")
def book_page():
    d = request.get_json(force=True)
    proj = normalize(d.get("project"))
    return jsonify(svg=B.page_svg(proj, int(d["n"]), resolver(proj), bool(d.get("show_guides"))))


@app.post("/api/book")
def book():
    proj = normalize(request.get_json(force=True))
    if not proj["designs"]:
        return jsonify(error="Sách chưa có tranh nào."), 400
    pdf, info = B.build_book(proj, resolver(proj))
    name = f"{safe_name(proj['title'], 'interior')}_interior_{time.strftime('%Y%m%d-%H%M%S')}.pdf"
    resp = pdf_response(pdf, name)
    resp.headers["X-Book-Info"] = json.dumps(info)
    resp.headers["Access-Control-Expose-Headers"] = "X-Book-Info"
    return resp


# ----------------------------- bia -----------------------------
def cover_inputs(proj):
    total = len(B.plan_pages(proj))
    i = int(proj["cover"].get("front", 0))
    design = item_design(proj["designs"][i]) if 0 <= i < len(proj["designs"]) else None
    return design, total


@app.post("/api/cover/preview")
def cover_preview():
    proj = normalize(request.get_json(force=True))
    design, total = cover_inputs(proj)
    svg, cg = cover_svg(proj, design, total, guides=True)
    return jsonify(svg=svg, page_count=total, spine_in=cg["spine_in"], size_in=cg["size_in"],
                   spine_text=cg["spine_text"])


@app.post("/api/cover")
def cover():
    proj = normalize(request.get_json(force=True))
    design, total = cover_inputs(proj)
    pdf, cg = cover_pdf(proj, design, total)
    return pdf_response(pdf, f"{safe_name(proj['title'], 'book')}_cover_{total}p.pdf")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"Hatch Studio dang chay: http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
