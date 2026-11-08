"""Seed demo data for FarmConnect. All demo data is clearly labelled DEMO.

Run: python3 manage.py seed
Idempotent-ish: it flushes existing demo rows first via manage flush if needed.
"""
from __future__ import annotations

from datetime import date

from core import db
from apps.accounts import models as acc
from apps.products import models as pm

# Maharashtra product categories
CATEGORIES = [
    ("Vegetables", "सब्ज़ियाँ", "भाजीपाला", "vegetables", "🥬"),
    ("Fruits", "फल", "फळे", "fruits", "🍎"),
    ("Grains", "अनाज", "धान्य", "grains", "🌾"),
    ("Pulses", "दालें", "कडधान्य", "pulses", "🫘"),
    ("Oilseeds", "तिलहन", "तेलबिया", "oilseeds", "🌻"),
    ("Spices", "मसाले", "मसाले", "spices", "🌶️"),
    ("Flowers", "फूल", "फुले", "flowers", "🌸"),
    ("Dairy", "डेयरी", "दुग्धजन्य", "dairy", "🥛"),
    ("Organic", "जैविक", "सेंद्रिय", "organic", "🌱"),
    ("Seeds", "बीज", "बियाणे", "seeds", "🌰"),
    ("Other", "अन्य", "इतर", "other", "📦"),
]

# Demo APMC market prices (clearly demo; real integration uses AGMARKNET/data.gov.in)
MARKET_PRICES = [
    ("Onion", "Red", "Lasalgaon APMC", "Nashik", 1600, 2100, 1900, "2026-11-06"),
    ("Onion", "Red", "Jalgaon APMC", "Jalgaon", 1500, 2000, 1800, "2026-11-06"),
    ("Wheat", "Lokwan", "Pune APMC", "Pune", 2300, 2700, 2500, "2026-11-05"),
    ("Tomato", "Hybrid", "Pune APMC", "Pune", 800, 1400, 1100, "2026-11-06"),
    ("Soybean", "Yellow", "Latur APMC", "Latur", 4200, 4800, 4500, "2026-11-05"),
    ("Cotton", "Long", "Jalgaon APMC", "Jalgaon", 6800, 7400, 7100, "2026-11-04"),
]


def run():
    print("Seeding DEMO data ...")
    _seed_categories()
    _seed_market_prices()
    _seed_users_and_products()
    print("\n✓ Demo data seeded.")
    print("  Admin : 9000000000 / admin1234")
    print("  Farmer: 9811111111 / farmer1234")
    print("  Buyer : 9822222222 / buyer1234")


def _seed_categories():
    cats = db.Table("product_categories")
    for i, (en, hi, mr, slug, icon) in enumerate(CATEGORIES):
        if not cats.get(slug=slug):
            cats.insert(name_en=en, name_hi=hi, name_mr=mr, slug=slug,
                        icon=icon, sort_order=i, is_active=1)
    print(f"  ✓ {len(CATEGORIES)} categories")


def _seed_market_prices():
    mp = db.Table("market_prices")
    if mp.count() == 0:
        for commodity, variety, market, district, mn, mx, modal, d in MARKET_PRICES:
            mp.insert(commodity=commodity, variety=variety, market=market,
                      district=district, min_price=str(mn), max_price=str(mx),
                      modal_price=str(modal), unit="quintal", arrival_date=d,
                      source="DEMO (AGMARKNET format)")
        print(f"  ✓ {len(MARKET_PRICES)} market prices (DEMO)")


def _ensure_user(role, full_name, mobile, email, password, **profile):
    existing = acc.get_user_by_mobile(mobile)
    if existing:
        return existing["id"]
    uid = acc.create_user(role=role, full_name=full_name, mobile=mobile,
                          email=email, password=password,
                          is_staff=(role == "admin"))
    return uid


def _seed_users_and_products():
    # Admin
    _ensure_user("admin", "FarmConnect Admin", "9000000000",
                 "admin@farmconnect.example", "admin1234")

    # Farmer in Erandol, Jalgaon
    fuid = _ensure_user("farmer", "Ramesh Patil", "9811111111",
                        "ramesh@example.com", "farmer1234")
    farmer = acc.get_farmer_by_user(fuid)
    if not farmer:
        fid = acc.create_farmer_profile(
            fuid, display_name="Ramesh Patil (DEMO)", village="Erandol",
            taluka="Erandol", district="Jalgaon", state="Maharashtra",
            pincode="425109", main_crops="Onion, Wheat, Cotton",
            verification_level="farm_verified", experience_years=12,
            bio="DEMO farmer from Erandol, Jalgaon growing onions and wheat.",
            rating_avg="4.6", rating_count="18",
        )
    else:
        fid = farmer["id"]

    # A second demo farmer (Nashik)
    fuid2 = _ensure_user("farmer", "Sita More", "9833333333",
                         "sita@example.com", "farmer1234")
    f2 = acc.get_farmer_by_user(fuid2)
    if not f2:
        fid2 = acc.create_farmer_profile(
            fuid2, display_name="Sita More (DEMO)", village="Pimpalgaon",
            taluka="Niphad", district="Nashik", main_crops="Tomato, Onion, Grapes",
            verification_level="identity_verified", rating_avg="4.3", rating_count="9",
            bio="DEMO farmer from Nashik.",
        )
    else:
        fid2 = f2["id"]

    # Buyer in Pune
    _ensure_user("buyer", "Vijay Traders", "9822222222",
                 "vijay@example.com", "buyer1234")
    buyer = acc.get_buyer_by_user(acc.get_user_by_mobile("9822222222")["id"])
    if not buyer:
        acc.create_buyer_profile(
            acc.get_user_by_mobile("9822222222")["id"],
            buyer_type="wholesaler", business_name="Vijay Traders (DEMO)",
            city="Pune", district="Pune", state="Maharashtra", pincode="411001",
            business_address="Market Yard, Pune",
        )

    cats = db.Table("product_categories")
    veg = cats.get(slug="vegetables")
    grains = cats.get(slug="grains")

    # Only create products if the farmer has none
    if not pm.products_by_farmer(fid):
        # Onion — the acceptance-test product
        onion = pm.create_product(
            farmer_id=fid, category_id=veg["id"], name="Onion",
            description="Fresh Grade A red onions, directly from the farm in Erandol, Jalgaon. (DEMO)",
            grade="grade_a", quality_notes="Uniform size, well cured",
            farming_method="conventional", unit="quintal", price="1800",
            price_negotiable=1, min_order_qty="5", sales_channel="both",
            listing_type="available", status="active",
            harvest_date="2026-11-05", packaging_info="50 kg jute bags",
            pickup_available=1, delivery_available=1, village="Erandol",
            taluka="Erandol", district="Jalgaon", pincode="425109",
        )
        pm.add_stock(onion, "50", note="Initial DEMO stock")

        wheat = pm.create_product(
            farmer_id=fid, category_id=grains["id"], name="Wheat",
            description="Lokwan wheat — upcoming harvest (DEMO).",
            grade="grade_a", farming_method="conventional", unit="quintal",
            price="2500", min_order_qty="10", sales_channel="wholesale",
            listing_type="upcoming_harvest", status="active",
            expected_availability="2027-01-15", estimated_quantity="100",
            expected_price="2500", village="Erandol", taluka="Erandol",
            district="Jalgaon",
        )

    if not pm.products_by_farmer(fid2):
        tomato = pm.create_product(
            farmer_id=fid2, category_id=veg["id"], name="Tomato",
            description="Fresh hybrid tomatoes from Nashik (DEMO).",
            grade="grade_b", farming_method="conventional", unit="kg",
            price="22", min_order_qty="50", sales_channel="both",
            status="active", district="Nashik", village="Pimpalgaon",
            taluka="Niphad", pickup_available=1, delivery_available=1,
        )
        pm.add_stock(tomato, "800", note="Initial DEMO stock")

    print("  ✓ demo users + products (onion @ ₹1800/quintal in Erandol, Jalgaon)")
