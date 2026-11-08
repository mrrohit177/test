#!/usr/bin/env python3
"""Render key FarmConnect pages to static HTML snapshots for visual preview.

This drives the WSGI app in-process (no live server needed) and writes
self-contained HTML into preview/ with CSS inlined and media embedded as
data URIs, so the pages display correctly in a read-only file viewer.

Usage: python3 make_preview.py
"""
from __future__ import annotations

import base64
import io
import mimetypes
import re
import sys
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import settings  # noqa: E402
import manage  # noqa: E402

manage._load_routes()
from core.wsgi import application  # noqa: E402
from core import db  # noqa: E402

PREVIEW_DIR = BASE_DIR / "preview"


class Client:
    def __init__(self):
        self.jar = SimpleCookie()

    def req(self, path, method="GET", data=None):
        cap = {}

        def sr(status, headers):
            cap["status"] = status
            cap["headers"] = headers

        body = urlencode(data).encode() if data else b""
        ctype = "application/x-www-form-urlencoded" if data else ""
        qs = ""
        if "?" in path:
            path, qs = path.split("?", 1)
        env = {
            "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": qs,
            "wsgi.input": io.BytesIO(body), "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": ctype,
            "HTTP_COOKIE": "; ".join(f"{k}={m.value}" for k, m in self.jar.items()),
        }
        out = b"".join(application(env, sr))
        for k, v in cap["headers"]:
            if k.lower() == "set-cookie":
                self.jar.load(v)
        loc = dict((k.lower(), v) for k, v in cap["headers"]).get("location")
        return int(cap["status"][:3]), out.decode("utf-8", "replace"), loc

    def login(self, mobile, pw):
        _, body, _ = self.req("/login")
        m = re.search(r'name="csrf_token" value="([^"]+)"', body)
        self.req("/login", "POST", {"csrf_token": m.group(1),
                                    "identifier": mobile, "password": pw})


# --- asset inlining ---------------------------------------------------------
def _css_bundle():
    css = ""
    for name in ("style.css", "dashboard.css"):
        p = settings.STATIC_DIR / "css" / name
        if p.exists():
            css += f"\n/* {name} */\n" + p.read_text()
    return css


def _data_uri(media_rel):
    p = settings.MEDIA_DIR / media_rel
    if not p.exists():
        return None
    mime, _ = mimetypes.guess_type(str(p))
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime or 'image/png'};base64,{b64}"


def inline(html, css):
    # replace the two stylesheet links with one inline <style>
    html = re.sub(
        r'<link rel="stylesheet" href="/static/css/[^"]+">', "", html, count=0
    )
    html = html.replace("</head>", f"<style>{css}</style>\n</head>", 1)
    # drop the JS (not needed for a static snapshot) but keep the menu button inert
    html = re.sub(r'<script src="/static/js/[^"]+"></script>', "", html)
    # embed media images as data URIs
    def repl(m):
        uri = _data_uri(m.group(1))
        return f'src="{uri}"' if uri else 'src=""'
    html = re.sub(r'src="/media/([^"]+)"', repl, html)
    # add a banner noting this is a static snapshot
    banner = (
        '<div style="background:#f9a825;color:#3a2c00;text-align:center;'
        'padding:8px;font:600 14px sans-serif">📸 Static preview snapshot — '
        'links are not clickable. Run <code>python3 manage.py runserver</code> '
        'locally for the live site.</div>'
    )
    html = html.replace("<body>", "<body>\n" + banner, 1)
    return html


PAGES = [
    ("01_home", "/", None),
    ("02_register_choice", "/register", None),
    ("03_register_farmer", "/register/farmer", None),
    ("04_login", "/login", None),
    ("05_browse_products", "/products", None),
    ("06_categories", "/categories", None),
    ("07_find_farmers", "/farmers", None),
    ("08_market_prices", "/market-prices", None),
    ("09_how_it_works", "/how-it-works", None),
]


def run():
    PREVIEW_DIR.mkdir(exist_ok=True)
    css = _css_bundle()

    anon = Client()
    index_links = []

    def save(slug, title, html):
        html = inline(html, css)
        (PREVIEW_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
        index_links.append((slug, title))
        print(f"  ✓ {slug}.html")

    # public pages
    for slug, path, _ in PAGES:
        s, body, _ = anon.req(path)
        if s == 200:
            save(slug, path, body)

    # a product detail page
    prod = db.query_one("SELECT id, name FROM products WHERE status='active' LIMIT 1")
    if prod:
        s, body, _ = anon.req(f"/products/{prod['id']}")
        if s == 200:
            save("10_product_detail", f"Product: {prod['name']}", body)

    # a farmer public profile
    farmer = db.query_one("SELECT id, display_name FROM farmer_profiles LIMIT 1")
    if farmer:
        s, body, _ = anon.req(f"/farmers/{farmer['id']}")
        if s == 200:
            save("11_farmer_profile", f"Farmer: {farmer['display_name']}", body)

    # farmer dashboard
    fc = Client(); fc.login("9811111111", "farmer1234")
    for slug, path, title in [
        ("12_farmer_dashboard", "/dashboard", "Farmer Dashboard"),
        ("13_farmer_products", "/farmer/products", "My Products"),
        ("14_add_product", "/farmer/products/new", "Add Product"),
        ("15_farmer_inventory", "/farmer/inventory", "Manage Inventory"),
    ]:
        s, body, _ = fc.req(path)
        if s == 200:
            save(slug, title, body)

    # buyer dashboard
    bc = Client(); bc.login("9822222222", "buyer1234")
    s, body, _ = bc.req("/dashboard")
    if s == 200:
        save("16_buyer_dashboard", "Buyer Dashboard", body)

    # admin dashboard
    ac = Client(); ac.login("9000000000", "admin1234")
    for slug, path, title in [
        ("17_admin_overview", "/admin", "Admin Overview"),
        ("18_admin_farmers", "/admin/farmers", "Admin · Farmers"),
        ("19_admin_reports", "/admin/reports", "Admin · Reports"),
    ]:
        s, body, _ = ac.req(path)
        if s == 200:
            save(slug, title, body)

    # index page listing all snapshots
    items = "\n".join(
        f'<li><a href="{slug}.html">{title}</a> '
        f'<span style="color:#888">({slug})</span></li>'
        for slug, title in index_links
    )
    index_html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>FarmConnect — Preview Index</title>
<style>body{{font:16px/1.6 sans-serif;max-width:720px;margin:40px auto;padding:0 20px;color:#2e2e2e}}
h1{{color:#1b5e20}} li{{margin:.4rem 0}} a{{color:#1b5e20}}
.note{{background:#e8f5e9;padding:12px 16px;border-radius:8px;border-left:4px solid #1b5e20}}</style>
</head><body>
<h1>🌾 FarmConnect — Preview Snapshots</h1>
<p class="note">These are static HTML snapshots of the running app (CSS inlined,
images embedded). Open each file in the file explorer. Links inside are inert —
run <code>python3 manage.py runserver</code> locally for the fully interactive site.</p>
<h3>Pages ({len(index_links)})</h3>
<ol>{items}</ol>
</body></html>"""
    (PREVIEW_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"\n✓ {len(index_links)} snapshots written to preview/")
    print("  Open preview/index.html in the file explorer.")


if __name__ == "__main__":
    run()
