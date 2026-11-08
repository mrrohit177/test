#!/usr/bin/env python3
"""FarmConnect management CLI.

Usage:
    python3 manage.py migrate      # create database + tables
    python3 manage.py seed         # load demo data (clearly marked DEMO)
    python3 manage.py runserver    # start the development server
    python3 manage.py createadmin  # interactively create an admin user
    python3 manage.py test         # run the test suite
    python3 manage.py flush        # drop all data (keeps schema)
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import settings  # noqa: E402


def cmd_migrate():
    from core import db

    settings.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = (BASE_DIR / "core" / "schema.sql").read_text(encoding="utf-8")
    db.executescript(schema)
    print(f"✓ Database ready at {settings.DATABASE_PATH}")
    print("✓ All tables created / verified.")


def cmd_seed():
    import seed_data

    seed_data.run()


def cmd_runserver():
    _load_routes()
    from wsgiref.simple_server import make_server, WSGIRequestHandler

    from core.wsgi import application

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write(
                f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n"
            )

    host, port = settings.HOST, settings.PORT
    print(f"\n🌾 FarmConnect running at http://{host}:{port}")
    print("   Press Ctrl+C to stop.\n")
    httpd = make_server(host, port, application, handler_class=QuietHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def cmd_createadmin():
    from apps.accounts import models as acc

    print("Create an admin user:")
    full_name = input("  Full name: ").strip()
    mobile = input("  Mobile (10 digits): ").strip()
    email = input("  Email: ").strip()
    import getpass

    password = getpass.getpass("  Password: ")
    user_id = acc.create_user(
        role="admin", full_name=full_name, mobile=mobile, email=email,
        password=password, is_staff=True,
    )
    print(f"✓ Admin created (id={user_id})")


def cmd_flush():
    from core import db

    tables = [
        "audit_logs", "transport_requests", "market_prices", "notifications",
        "complaints", "reviews", "wishlists", "order_items", "orders",
        "negotiation_offers", "negotiations", "enquiries", "inventory_movements",
        "product_inventory", "product_images", "products", "product_categories",
        "buyer_profiles", "farmer_profiles", "addresses", "sessions", "users",
    ]
    for t in tables:
        try:
            db.execute(f"DELETE FROM {t}")
        except Exception as e:  # noqa: BLE001
            print(f"  (skip {t}: {e})")
    print("✓ All data flushed (schema kept).")


def cmd_test():
    import unittest

    loader = unittest.TestLoader()
    suite = loader.discover(str(BASE_DIR / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


def _load_routes():
    """Import every app's routes module so the global router is populated."""
    import apps.accounts.routes  # noqa: F401
    import apps.products.routes  # noqa: F401
    import apps.marketplace.routes  # noqa: F401
    import apps.enquiries.routes  # noqa: F401
    import apps.orders.routes  # noqa: F401
    import apps.dashboard.routes  # noqa: F401
    import apps.notifications.routes  # noqa: F401
    import apps.logistics.routes  # noqa: F401
    import apps.market_prices.routes  # noqa: F401


COMMANDS = {
    "migrate": cmd_migrate,
    "seed": cmd_seed,
    "runserver": cmd_runserver,
    "createadmin": cmd_createadmin,
    "flush": cmd_flush,
    "test": cmd_test,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
