"""Unit/integration tests for auth, roles, products, search, inventory, admin."""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

_tmp = tempfile.mkdtemp(prefix="fc_unit_")
os.environ["FARMCONNECT_DB"] = str(Path(_tmp) / "test.sqlite3")

import settings  # noqa: E402
settings.DATABASE_PATH = Path(os.environ["FARMCONNECT_DB"])

import manage  # noqa: E402
from core import db, security  # noqa: E402


def _reset_db():
    db.close_connection()
    # physically remove the db file for a clean slate each test
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(settings.DATABASE_PATH) + suffix)
        if p.exists():
            p.unlink()
    db.executescript((BASE_DIR / "core" / "schema.sql").read_text())
    import seed_data
    seed_data._seed_categories()


class Client:
    def __init__(self):
        self.cookies = SimpleCookie()
        from core.wsgi import application
        self.app = application

    def request(self, path, method="GET", data=None):
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = headers

        body = urlencode(data).encode() if data else b""
        ctype = "application/x-www-form-urlencoded" if data else ""
        qs = ""
        if "?" in path:
            path, qs = path.split("?", 1)
        environ = {
            "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": qs,
            "wsgi.input": io.BytesIO(body), "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": ctype,
            "HTTP_COOKIE": "; ".join(f"{k}={m.value}" for k, m in self.cookies.items()),
        }
        out = b"".join(self.app(environ, start_response))
        for k, v in captured["headers"]:
            if k.lower() == "set-cookie":
                self.cookies.load(v)
        loc = dict((k.lower(), v) for k, v in captured["headers"]).get("location")
        return int(captured["status"][:3]), out.decode("utf-8", "replace"), loc

    def get(self, p):
        return self.request(p, "GET")

    def post(self, p, data=None):
        return self.request(p, "POST", data=data)

    def csrf(self, path):
        import re
        _, body, _ = self.get(path)
        m = re.search(r'name="csrf_token" value="([^"]+)"', body)
        return m.group(1) if m else None

    def register_farmer(self, mobile="9811110000", district="Jalgaon"):
        tok = self.csrf("/register/farmer")
        return self.post("/register/farmer", data={
            "csrf_token": tok, "full_name": "Test Farmer", "mobile": mobile,
            "email": f"f{mobile}@x.com", "password": "secret123",
            "confirm_password": "secret123", "village": "V", "taluka": "T",
            "district": district, "state": "MH", "pincode": "425109",
            "main_crops": "Onion", "preferred_language": "en"})

    def register_buyer(self, mobile="9822220000"):
        tok = self.csrf("/register/buyer")
        return self.post("/register/buyer", data={
            "csrf_token": tok, "full_name": "Test Buyer", "mobile": mobile,
            "email": f"b{mobile}@x.com", "password": "secret123",
            "confirm_password": "secret123", "buyer_type": "wholesaler",
            "city": "Pune", "district": "Pune", "state": "MH", "pincode": "411001"})

    def add_product(self, name="Onion", price="1800", qty="50", moq="5"):
        tok = self.csrf("/farmer/products/new")
        return self.post("/farmer/products/new", data={
            "csrf_token": tok, "name": name, "category_id": "",
            "description": "d", "grade": "grade_a", "farming_method": "conventional",
            "unit": "quintal", "price": price, "price_negotiable": "1",
            "quantity": qty, "min_order_qty": moq, "sales_channel": "both",
            "listing_type": "available", "pickup_available": "1",
            "delivery_available": "1", "village": "V", "taluka": "T",
            "district": "Jalgaon"})


class BaseCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manage._load_routes()
    def setUp(self):
        _reset_db()


class AuthTests(BaseCase):
    def test_password_hashing(self):
        h = security.hash_password("hunter2")
        self.assertTrue(security.verify_password("hunter2", h))
        self.assertFalse(security.verify_password("wrong", h))
        self.assertNotIn("hunter2", h)  # never plaintext

    def test_farmer_registration_and_login(self):
        c = Client()
        status, _, loc = c.register_farmer()
        self.assertEqual(status, 303)
        user = db.query_one("SELECT * FROM users WHERE mobile='9811110000'")
        self.assertEqual(user["role"], "farmer")
        self.assertNotEqual(user["password_hash"], "secret123")

    def test_duplicate_mobile_rejected(self):
        Client().register_farmer(mobile="9811110001")
        c2 = Client()
        status, body, loc = c2.register_farmer(mobile="9811110001")
        self.assertEqual(status, 200)  # re-render with error, not redirect
        self.assertIn("already registered", body)

    def test_login_logout(self):
        Client().register_farmer(mobile="9811110002")
        c = Client()
        tok = c.csrf("/login")
        status, _, loc = c.post("/login", data={
            "csrf_token": tok, "identifier": "9811110002", "password": "secret123"})
        self.assertEqual(status, 303)
        status, _, loc = c.post("/logout", data={"csrf_token": c.csrf("/dashboard")})
        # after logout, dashboard redirects to login
        status, _, loc = c.get("/dashboard")
        self.assertEqual(status, 303)
        self.assertIn("/login", loc)

    def test_bad_credentials(self):
        Client().register_farmer(mobile="9811110003")
        c = Client()
        tok = c.csrf("/login")
        status, body, _ = c.post("/login", data={
            "csrf_token": tok, "identifier": "9811110003", "password": "nope"})
        self.assertIn("Invalid credentials", body)


class RoleTests(BaseCase):
    def test_buyer_cannot_access_farmer_pages(self):
        c = Client()
        c.register_buyer(mobile="9822220001")
        status, _, _ = c.get("/farmer/products/new")
        self.assertEqual(status, 403)

    def test_anonymous_redirected_from_dashboard(self):
        c = Client()
        status, _, loc = c.get("/dashboard")
        self.assertEqual(status, 303)
        self.assertIn("/login", loc)

    def test_non_admin_cannot_access_admin(self):
        c = Client()
        c.register_farmer(mobile="9811110004")
        status, _, _ = c.get("/admin")
        self.assertEqual(status, 403)

    def test_csrf_required(self):
        c = Client()
        c.register_farmer(mobile="9811110005")
        # POST without csrf token -> 403
        status, _, _ = c.post("/farmer/products/new", data={"name": "X"})
        self.assertEqual(status, 403)


class ProductTests(BaseCase):
    def test_create_and_appears_in_search(self):
        c = Client()
        c.register_farmer(mobile="9811110006")
        status, _, _ = c.add_product(name="Potato", price="1200")
        self.assertEqual(status, 303)
        p = db.query_one("SELECT * FROM products WHERE name='Potato'")
        self.assertIsNotNone(p)
        # public search
        anon = Client()
        _, body, _ = anon.get("/products?q=potato")
        self.assertIn("Potato", body)

    def test_edit_product(self):
        c = Client()
        c.register_farmer(mobile="9811110007")
        c.add_product(name="Garlic", price="5000")
        p = db.query_one("SELECT * FROM products WHERE name='Garlic'")
        tok = c.csrf(f"/farmer/products/{p['id']}/edit")
        status, _, _ = c.post(f"/farmer/products/{p['id']}/edit", data={
            "csrf_token": tok, "name": "Garlic", "category_id": "",
            "description": "updated", "grade": "grade_a",
            "farming_method": "conventional", "unit": "quintal", "price": "5500",
            "price_negotiable": "1", "min_order_qty": "1", "sales_channel": "both",
            "pickup_available": "1", "district": "Jalgaon"})
        self.assertEqual(status, 303)
        p2 = db.query_one("SELECT * FROM products WHERE id=?", [p["id"]])
        self.assertEqual(float(p2["price"]), 5500.0)

    def test_delete_is_soft(self):
        c = Client()
        c.register_farmer(mobile="9811110008")
        c.add_product(name="Chilli")
        p = db.query_one("SELECT * FROM products WHERE name='Chilli'")
        tok = c.csrf("/farmer/products")
        c.post(f"/farmer/products/{p['id']}/delete", data={"csrf_token": tok})
        p2 = db.query_one("SELECT * FROM products WHERE id=?", [p["id"]])
        self.assertEqual(p2["status"], "deleted")

    def test_search_filters_by_price(self):
        c = Client()
        c.register_farmer(mobile="9811110009")
        c.add_product(name="Cheap", price="100")
        c.add_product(name="Pricey", price="9000")
        anon = Client()
        _, body, _ = anon.get("/products?max_price=500")
        self.assertIn("Cheap", body)
        self.assertNotIn("Pricey", body)


class InventoryTests(BaseCase):
    def _make_product(self, qty="50"):
        c = Client()
        c.register_farmer(mobile="9811110010")
        c.add_product(name="Onion", qty=qty)
        return c, db.query_one("SELECT * FROM products WHERE name='Onion'")

    def test_initial_stock(self):
        _, p = self._make_product("50")
        inv = db.query_one("SELECT * FROM product_inventory WHERE product_id=?", [p["id"]])
        self.assertEqual(float(inv["available_qty"]), 50.0)

    def test_cannot_oversell(self):
        from apps.products import models as pm
        _, p = self._make_product("10")
        with self.assertRaises(pm.InventoryError):
            pm.reserve_stock(p["id"], 100)

    def test_reservation_and_release(self):
        from apps.products import models as pm
        _, p = self._make_product("50")
        pm.reserve_stock(p["id"], 20)
        inv = pm.get_inventory(p["id"])
        self.assertEqual(float(inv["available_qty"]), 30.0)
        self.assertEqual(float(inv["reserved_qty"]), 20.0)
        pm.release_stock(p["id"], 20)
        inv = pm.get_inventory(p["id"])
        self.assertEqual(float(inv["available_qty"]), 50.0)
        self.assertEqual(float(inv["reserved_qty"]), 0.0)

    def test_stock_never_negative_via_adjust(self):
        from apps.products import models as pm
        _, p = self._make_product("5")
        pm.adjust_stock(p["id"], 0)  # drop to zero
        inv = pm.get_inventory(p["id"])
        self.assertEqual(float(inv["available_qty"]), 0.0)
        self.assertGreaterEqual(float(inv["available_qty"]), 0.0)

    def test_order_cancellation_releases_stock(self):
        from apps.orders import models as om
        from apps.products import models as pm
        from apps.accounts import models as acc
        fc, p = self._make_product("50")
        bc = Client(); bc.register_buyer(mobile="9822220002")
        buyer = acc.get_buyer_by_user(acc.get_user_by_mobile("9822220002")["id"])
        oid, num = om.create_order(buyer_id=buyer["id"], farmer_id=p["farmer_id"],
                                   product=p, quantity="20", unit_price="1800")
        inv = pm.get_inventory(p["id"])
        self.assertEqual(float(inv["reserved_qty"]), 20.0)
        om.transition(oid, "cancelled", actor_role="buyer")
        inv = pm.get_inventory(p["id"])
        self.assertEqual(float(inv["reserved_qty"]), 0.0)
        self.assertEqual(float(inv["available_qty"]), 50.0)


class AdminTests(BaseCase):
    def _login_admin(self):
        from apps.accounts import models as acc
        acc.create_user(role="admin", full_name="Admin", mobile="9000000000",
                        email="admin@x.com", password="admin1234", is_staff=True)
        c = Client()
        tok = c.csrf("/login")
        c.post("/login", data={"csrf_token": tok, "identifier": "9000000000",
                               "password": "admin1234"})
        return c

    def test_admin_dashboard_accessible(self):
        c = self._login_admin()
        status, body, _ = c.get("/admin")
        self.assertEqual(status, 200)
        self.assertIn("Admin Overview", body)

    def test_admin_can_verify_farmer(self):
        Client().register_farmer(mobile="9811110011")
        farmer = db.query_one("SELECT * FROM farmer_profiles LIMIT 1")
        c = self._login_admin()
        tok = c.csrf("/admin/farmers")
        status, _, _ = c.post(f"/admin/farmers/{farmer['id']}/verify", data={
            "csrf_token": tok, "verification_level": "farm_verified"})
        self.assertEqual(status, 303)
        f2 = db.query_one("SELECT * FROM farmer_profiles WHERE id=?", [farmer["id"]])
        self.assertEqual(f2["verification_level"], "farm_verified")


if __name__ == "__main__":
    unittest.main(verbosity=2)
