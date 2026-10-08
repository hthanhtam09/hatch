"""
Mot du an = mot cuon sach. Luu thanh JSON trong data/project.json.
normalize() dien gia tri mac dinh de code phia sau khong phai kiem tra tung khoa.
"""
import copy
import time

DEFAULTS = {
    "title": "",
    "subtitle": "",
    "author": "",
    "publisher": "",
    "isbn": "",
    "year": None,
    "back_text": "",
    "settings": {
        "bleed": True,
        "padding_in": 0.25,
        "extra_margin_in": 0.0,
        "page_numbers": True,
        "blank_back": True,
        "title_page": True,
        "copyright_page": True,
        "howto_page": True,
        "warmup_page": True,
        "training_pages": True,
        "include_keys": False,
        "keys_per_page": 4,
        "pad_to_min": True,
    },
    "style": {},
    "cover": {"front": 0, "theme": "light", "paper": "white", "front_mode": "key"},
    "designs": [],   # {uid, image_id, name, engine:{}, edits:[], frame:bool, thumb}
}


def normalize(p):
    p = p or {}
    out = copy.deepcopy(DEFAULTS)
    for k, v in p.items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k].update(v)
        else:
            out[k] = v
    if not out["year"]:
        out["year"] = time.localtime().tm_year
    return out
