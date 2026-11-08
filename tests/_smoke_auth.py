"""Authenticated full-page smoke test against the seeded dev database."""
import io
import re
import sys
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import manage  # noqa: E402
manage._load_routes()
from core.wsgi import application  # noqa: E402
from core import db  # noqa: E402


class C:
    def __init__(self):
        self.jar = SimpleCookie()

    def req(self, path, method="GET", data=None):
        cap = {}
        def sr(s, h): cap["s"] = s; cap["h"] = h
        body = urlencode(data).encode() if data else b""
        ct = "application/x-www-form-urlencoded" if data else ""
        qs = ""
        if "?" in path:
            path, qs = path.split("?", 1)
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": qs,
               "wsgi.input": io.BytesIO(body), "CONTENT_LENGTH": str(len(body)),
               "CONTENT_TYPE": ct,
               "HTTP_COOKIE": "; ".join(f"{k}={m.value}" for k, m in self.jar.items())}
        out = b"".join(application(env, sr))
        for k, v in cap["h"]:
            if k.lower() == "set-cookie":
                self.jar.load(v)
        loc = dict((k.lower(), v) for k, v in cap["h"]).get("location")
        return int(cap["s"][:3]), out.decode("utf-8", "replace"), loc

    def login(self, mobile, pw):
        _, body, _ = self.req("/login")
        tok = re.search(r'name="csrf_token" value="([^"]+)"', body).group(1)
        return self.req("/login", "POST", {"csrf_token": tok, "identifier": mobile, "password": pw})


def check(label, pages, client):
    print(f"\n=== {label} ===")
    allok = True
    for p in pages:
        s, body, loc = client.req(p)
        leftover = "{{" in body or "{%" in body
        bad = not (s in (200, 303)) or leftover
        if bad:
            allok = False
        print(f"  {s} leftover={leftover}{'  <-- CHECK' if bad else ''}  {p}")
    return allok


farmer_pages = ["/dashboard", "/farmer/products", "/farmer/products/new",
                "/farmer/inventory", "/farmer/enquiries", "/farmer/negotiations",
                "/farmer/orders", "/farmer/sales", "/profile", "/settings",
                "/notifications", "/transport", "/transport/new"]
buyer_pages = ["/dashboard", "/buyer/enquiries", "/buyer/negotiations",
               "/buyer/orders", "/buyer/wishlist", "/buyer/history",
               "/profile", "/settings", "/notifications", "/transport"]
admin_pages = ["/admin", "/admin/farmers", "/admin/buyers", "/admin/products",
               "/admin/orders", "/admin/complaints", "/admin/reports"]

def main():
  ok = True
  fc = C(); print("farmer login:", fc.login("9811111111", "farmer1234")[0])
  ok &= check("FARMER", farmer_pages, fc)
  bc = C(); print("\nbuyer login:", bc.login("9822222222", "buyer1234")[0])
  ok &= check("BUYER", buyer_pages, bc)
  ac = C(); print("\nadmin login:", ac.login("9000000000", "admin1234")[0])
  ok &= check("ADMIN", admin_pages, ac)

  prod = db.query_one("SELECT id FROM products WHERE name='Onion' LIMIT 1")
  if prod:
      s, body, _ = bc.req(f"/products/{prod['id']}")
      print(f"\nproduct detail: {s} leftover={'{{' in body or '{%' in body}")

  print("\nRESULT:", "ALL OK" if ok else "ISSUES FOUND")


if __name__ == "__main__":
    main()
