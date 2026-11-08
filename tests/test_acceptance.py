"""End-to-end acceptance test driving the WSGI app like a real browser.

Covers the mandatory acceptance scenario:
  farmer registers (Erandol) -> lists onions -> buyer registers (Pune) ->
  searches -> enquires -> negotiates -> farmer accepts -> order created ->
  inventory reserved -> status progresses -> buyer completes -> history persists.
"""
from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Use a throwaway database for the test run.
_tmp = tempfile.mkdtemp(prefix="fc_test_")
os.environ["FARMCONNECT_DB"] = str(Path(_tmp) / "test.sqlite3")

import settings  # noqa: E402
settings.DATABASE_PATH = Path(os.environ["FARMCONNECT_DB"])

import manage  # noqa: E402
from core import db  # noqa: E402


class Client:
    """Minimal cookie-aware WSGI test client."""

    def __init__(self):
        self.cookies = SimpleCookie()
        from core.wsgi import application
        self.app = application

    def _cookie_header(self):
        return "; ".join(f"{k}={m.value}" for k, m in self.cookies.items())

    def _store_cookies(self, headers):
        for key, val in headers:
            if key.lower() == "set-cookie":
                self.cookies.load(val)

    def request(self, path, method="GET", data=None, multipart=None):
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = headers

        body = b""
        ctype = ""
        if multipart is not None:
            body, ctype = _encode_multipart(multipart)
        elif data is not None:
            body = urlencode(data).encode()
            ctype = "application/x-www-form-urlencoded"

        if "?" in path:
            path, qs = path.split("?", 1)
        else:
            qs = ""

        environ = {
            "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": qs,
            "wsgi.input": io.BytesIO(body), "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": ctype, "HTTP_COOKIE": self._cookie_header(),
        }
        out = b"".join(self.app(environ, start_response))
        self._store_cookies(captured["headers"])
        status = int(captured["status"][:3])
        location = dict((k.lower(), v) for k, v in captured["headers"]).get("location")
        return status, out.decode("utf-8", "replace"), location

    def get(self, path):
        return self.request(path, "GET")

    def post(self, path, data=None, multipart=None):
        return self.request(path, "POST", data=data, multipart=multipart)

    def csrf(self, path):
        """GET a page and extract its CSRF token."""
        _, body, _ = self.get(path)
        m = re.search(r'name="csrf_token" value="([^"]+)"', body)
        return m.group(1) if m else None


def _encode_multipart(fields):
    boundary = "----fctestboundary"
    lines = []
    for name, value in fields.items():
        if isinstance(value, tuple):  # file: (filename, bytes)
            filename, content = value
            lines.append(f"--{boundary}".encode())
            lines.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode())
            lines.append(b"Content-Type: image/png")
            lines.append(b"")
            lines.append(content)
        else:
            lines.append(f"--{boundary}".encode())
            lines.append(f'Content-Disposition: form-data; name="{name}"'.encode())
            lines.append(b"")
            lines.append(str(value).encode())
    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


# a tiny valid 1x1 PNG
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
       b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


class AcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manage._load_routes()  # populate the global router
        db.close_connection()
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(settings.DATABASE_PATH) + suffix)
            if p.exists():
                p.unlink()
        schema = (BASE_DIR / "core" / "schema.sql").read_text()
        db.executescript(schema)
        import seed_data
        # seed only categories + market prices (we create our own users)
        seed_data._seed_categories()
        seed_data._seed_market_prices()

    def test_full_scenario(self):
        farmer_c = Client()
        buyer_c = Client()

        # 1. Farmer registers from Erandol, Jalgaon
        token = farmer_c.csrf("/register/farmer")
        status, _, loc = farmer_c.post("/register/farmer", data={
            "csrf_token": token, "full_name": "Test Farmer",
            "mobile": "9700000001", "email": "tf@example.com",
            "password": "secret123", "confirm_password": "secret123",
            "village": "Erandol", "taluka": "Erandol", "district": "Jalgaon",
            "state": "Maharashtra", "pincode": "425109", "main_crops": "Onion",
            "preferred_language": "en",
        })
        self.assertEqual(status, 303)
        self.assertEqual(loc, "/dashboard")

        # 2. Farmer dashboard loads
        status, body, _ = farmer_c.get("/dashboard")
        self.assertEqual(status, 200)
        self.assertIn("Dashboard", body)

        # 3. Farmer adds 50 quintals of onions @ ₹1800, with a photo
        token = farmer_c.csrf("/farmer/products/new")
        status, _, loc = farmer_c.post("/farmer/products/new", multipart={
            "csrf_token": token, "name": "Onion", "category_id": "",
            "description": "Grade A red onions", "grade": "grade_a",
            "farming_method": "conventional", "unit": "quintal", "price": "1800",
            "price_negotiable": "1", "quantity": "50", "min_order_qty": "5",
            "sales_channel": "both", "listing_type": "available",
            "pickup_available": "1", "delivery_available": "1",
            "village": "Erandol", "taluka": "Erandol", "district": "Jalgaon",
            "images": ("onion.png", PNG),
        })
        self.assertEqual(status, 303, "product creation should redirect")

        # 4. photo saved + listing appears in marketplace
        product = db.query_one("SELECT * FROM products WHERE name='Onion'")
        self.assertIsNotNone(product)
        self.assertEqual(str(product["price"]), "1800")
        img = db.query_one("SELECT * FROM product_images WHERE product_id=?", [product["id"]])
        self.assertIsNotNone(img, "product image should be saved")
        inv = db.query_one("SELECT * FROM product_inventory WHERE product_id=?", [product["id"]])
        self.assertEqual(float(inv["available_qty"]), 50.0)

        # 5. listing in public marketplace search for 'onion'
        status, body, _ = buyer_c.get("/products?q=onion")
        self.assertEqual(status, 200)
        self.assertIn("Onion", body)

        # 6. Buyer registers from Pune
        token = buyer_c.csrf("/register/buyer")
        status, _, loc = buyer_c.post("/register/buyer", data={
            "csrf_token": token, "full_name": "Test Buyer",
            "mobile": "9700000002", "email": "tb@example.com",
            "password": "secret123", "confirm_password": "secret123",
            "buyer_type": "wholesaler", "city": "Pune", "district": "Pune",
            "state": "Maharashtra", "pincode": "411001",
        })
        self.assertEqual(status, 303)

        # 7-9. Buyer discovers listing and sends enquiry for 20 quintals @ 1750
        token = buyer_c.csrf(f"/products/{product['id']}")
        status, _, loc = buyer_c.post("/enquiries/create", data={
            "csrf_token": token, "product_id": product["id"],
            "required_qty": "20", "proposed_price": "1750",
            "delivery_district": "Pune", "message": "Need 20 quintals in Pune",
        })
        self.assertEqual(status, 303)
        neg_id = loc.split("/")[-1]

        # 10. Farmer receives enquiry (notification + enquiry row)
        enquiry = db.query_one("SELECT * FROM enquiries WHERE product_id=?", [product["id"]])
        self.assertIsNotNone(enquiry)
        self.assertEqual(float(enquiry["required_qty"]), 20.0)
        farmer_user = db.query_one("SELECT * FROM users WHERE mobile='9700000001'")
        notif = db.query_one("SELECT * FROM notifications WHERE user_id=? AND type='enquiry'",
                             [farmer_user["id"]])
        self.assertIsNotNone(notif, "farmer should be notified of enquiry")

        # 11. Negotiate: farmer counters at 1800
        token = farmer_c.csrf(f"/negotiations/{neg_id}")
        status, _, _ = farmer_c.post(f"/negotiations/{neg_id}/respond", data={
            "csrf_token": token, "action": "counter",
            "offered_qty": "20", "offered_price": "1800",
            "message": "Can do 20 quintals at 1800",
        })
        self.assertEqual(status, 303)

        # buyer accepts farmer's counteroffer
        token = buyer_c.csrf(f"/negotiations/{neg_id}")
        status, _, _ = buyer_c.post(f"/negotiations/{neg_id}/respond", data={
            "csrf_token": token, "action": "accept",
        })
        self.assertEqual(status, 303)

        # 12. verify accepted offer
        accepted = db.query_one(
            "SELECT * FROM negotiation_offers WHERE negotiation_id=? AND status='accepted'",
            [neg_id])
        self.assertIsNotNone(accepted)
        self.assertEqual(float(accepted["offered_price"]), 1800.0)

        # 13. Buyer converts accepted offer into an order
        token = buyer_c.csrf(f"/negotiations/{neg_id}")
        status, _, loc = buyer_c.post("/orders/create-from-offer", data={
            "csrf_token": token, "negotiation_id": neg_id,
            "fulfilment_method": "delivery",
        })
        self.assertEqual(status, 303)
        order_id = loc.split("/")[-1]
        order = db.query_one("SELECT * FROM orders WHERE id=?", [order_id])
        self.assertIsNotNone(order)
        self.assertTrue(order["order_number"].startswith("FC-"))
        self.assertEqual(order["status"], "pending")
        # total = 20 * 1800 = 36000
        self.assertEqual(float(order["product_amount"]), 36000.0)

        # 14. inventory reserved correctly (50 -> 30 available, 20 reserved)
        inv = db.query_one("SELECT * FROM product_inventory WHERE product_id=?", [product["id"]])
        self.assertEqual(float(inv["available_qty"]), 30.0)
        self.assertEqual(float(inv["reserved_qty"]), 20.0)

        # 15. Farmer progresses the order: accept -> confirm -> ready -> dispatch
        for new_status in ("accepted", "confirmed", "ready_for_pickup", "dispatched"):
            token = farmer_c.csrf(f"/orders/{order_id}")
            status, _, _ = farmer_c.post(f"/orders/{order_id}/status", data={
                "csrf_token": token, "status": new_status})
            self.assertEqual(status, 303, f"transition to {new_status}")
            row = db.query_one("SELECT status FROM orders WHERE id=?", [order_id])
            self.assertEqual(row["status"], new_status)

        # 16. Buyer sees updated status
        status, body, _ = buyer_c.get(f"/orders/{order_id}")
        self.assertEqual(status, 200)
        self.assertIn("Dispatched", body)

        # 17-18. Buyer confirms receipt -> completed
        token = buyer_c.csrf(f"/orders/{order_id}")
        status, _, _ = buyer_c.post(f"/orders/{order_id}/status", data={
            "csrf_token": token, "status": "completed"})
        self.assertEqual(status, 303)
        order = db.query_one("SELECT * FROM orders WHERE id=?", [order_id])
        self.assertEqual(order["status"], "completed")
        self.assertEqual(order["payment_status"], "paid")

        # inventory committed: reserved 20 -> 0, sold 20
        inv = db.query_one("SELECT * FROM product_inventory WHERE product_id=?", [product["id"]])
        self.assertEqual(float(inv["reserved_qty"]), 0.0)
        self.assertEqual(float(inv["sold_qty"]), 20.0)
        self.assertEqual(float(inv["available_qty"]), 30.0)

        # 19. both parties see transaction history
        status, body, _ = farmer_c.get("/farmer/sales")
        self.assertIn(order["order_number"], body)
        status, body, _ = buyer_c.get("/buyer/history")
        self.assertIn(order["order_number"], body)

    def test_persistence_after_reconnect(self):
        """Data survives a DB connection restart (seed categories persist)."""
        db.close_connection()
        row = db.query_one("SELECT COUNT(*) AS c FROM product_categories")
        self.assertGreaterEqual(row["c"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
