"""Public marketplace views: home, browse/search, product detail, categories, farmers."""
from __future__ import annotations

from core import db
from core.http import not_found
from core.views import render
from apps.products import models as pmodels

from . import queries


def home(request):
    district = None
    if request.user and request.user["role"] == "buyer":
        from apps.accounts.models import get_buyer_by_user
        bp = get_buyer_by_user(request.user["id"])
        district = bp["district"] if bp else None

    ctx = {
        "featured": queries.featured(8),
        "recent": queries.recent(8),
        "wholesale": queries.wholesale(4),
        "upcoming": queries.upcoming_harvests(4),
        "categories": pmodels.all_categories(),
        "near": queries.near_district(district, 4) if district else [],
        "near_district": district,
        "top_farmers": _top_farmers(6),
    }
    return render(request, "home.html", ctx)


def browse(request):
    page = max(1, int(request.GET("page", "1") or 1))
    per_page = 24
    sort = request.GET("sort", "recent")
    listing_type = request.GET("listing", "available")

    rows, total = queries.search(
        q=request.GET("q"),
        category_slug=request.GET("category"),
        district=request.GET("district"),
        grade=request.GET("grade"),
        method=request.GET("method"),
        channel=request.GET("channel"),
        min_price=request.GET("min_price"),
        max_price=request.GET("max_price"),
        verified_only=request.GET("verified") == "1",
        delivery_only=request.GET("delivery") == "1",
        listing_type=listing_type,
        sort=sort,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    ctx = {
        "products": rows,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "categories": pmodels.all_categories(),
        "districts": queries.distinct_districts(),
        "grades": [{"value": g, "label": pmodels.GRADE_LABELS[g]} for g in pmodels.GRADES],
        "filters": {
            "q": request.GET("q", ""),
            "category": request.GET("category", ""),
            "district": request.GET("district", ""),
            "grade": request.GET("grade", ""),
            "method": request.GET("method", ""),
            "channel": request.GET("channel", ""),
            "min_price": request.GET("min_price", ""),
            "max_price": request.GET("max_price", ""),
            "verified": request.GET("verified", ""),
            "delivery": request.GET("delivery", ""),
            "sort": sort,
            "listing": listing_type,
        },
        "query_string": request.query_string,
    }
    return render(request, "marketplace/browse.html", ctx)


def product_detail(request, id):
    product = queries.get_detail(id)
    if not product or product["status"] == "deleted":
        return not_found("Product not found")
    pmodels.increment_views(id)

    images = pmodels.get_images(id)
    inventory = pmodels.get_inventory(id)
    other = queries.by_farmer(product["farmer_id"], exclude=id, limit=4)

    # market price comparison (informational)
    comparison = _price_comparison(product)

    in_wishlist = False
    if request.user and request.user["role"] == "buyer":
        from apps.accounts.models import get_buyer_by_user
        bp = get_buyer_by_user(request.user["id"])
        if bp:
            in_wishlist = db.query_one(
                "SELECT 1 FROM wishlists WHERE buyer_id=? AND product_id=?",
                [bp["id"], id],
            ) is not None

    ctx = {
        "product": product,
        "images": images,
        "inventory": inventory,
        "other_products": other,
        "comparison": comparison,
        "in_wishlist": in_wishlist,
        "can_buy": bool(request.user and request.user["role"] == "buyer"),
        "unit_labels": pmodels.UNIT_LABELS,
    }
    return render(request, "marketplace/product_detail.html", ctx)


def categories_page(request):
    cats = pmodels.all_categories()
    # attach product counts
    for c in cats:
        c["count"] = db.query_one(
            "SELECT COUNT(*) AS n FROM products WHERE category_id=? AND status='active'",
            [c["id"]],
        )["n"]
    return render(request, "marketplace/categories.html", {"categories": cats})


def farmers_page(request):
    q = request.GET("q", "")
    district = request.GET("district", "")
    sql = """
        SELECT f.*, u.full_name, u.created_at AS member_since,
               (SELECT COUNT(*) FROM products p WHERE p.farmer_id=f.id AND p.status='active') AS product_count
        FROM farmer_profiles f JOIN users u ON u.id = f.user_id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND (f.display_name LIKE ? OR f.village LIKE ? OR f.district LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if district:
        sql += " AND f.district = ?"
        params.append(district)
    sql += " ORDER BY f.rating_avg DESC, product_count DESC LIMIT 60"
    farmers = db.query(sql, params)
    districts = [r["district"] for r in db.query(
        "SELECT DISTINCT district FROM farmer_profiles ORDER BY district") if r["district"]]
    return render(request, "marketplace/farmers.html", {
        "farmers": farmers, "q": q, "district": district, "districts": districts,
    })


def farmer_profile(request, farmer_id):
    from apps.accounts.models import get_farmer
    farmer = get_farmer(farmer_id)
    if not farmer:
        return not_found("Farmer not found")
    products = queries.by_farmer(farmer_id, limit=24)
    reviews = db.query(
        "SELECT r.*, u.full_name AS author_name FROM reviews r "
        "JOIN users u ON u.id = r.author_id "
        "WHERE r.target_type='farmer' AND r.target_id=? ORDER BY r.created_at DESC LIMIT 10",
        [farmer_id],
    )
    return render(request, "marketplace/farmer_profile.html", {
        "farmer": farmer, "products": products, "reviews": reviews,
    })


# --- static info pages ------------------------------------------------------
def about(request):
    return render(request, "pages/about.html")


def contact(request):
    if request.method == "POST":
        from core.views import add_message
        from core.http import redirect
        add_message(request, "success", "Thanks for reaching out — we'll get back to you soon.")
        return redirect("/contact")
    return render(request, "pages/contact.html")


def how_it_works(request):
    return render(request, "pages/how_it_works.html")


# --- helpers ----------------------------------------------------------------
def _top_farmers(limit):
    return db.query(
        "SELECT f.*, (SELECT COUNT(*) FROM products p WHERE p.farmer_id=f.id "
        "AND p.status='active') AS product_count "
        "FROM farmer_profiles f ORDER BY f.rating_avg DESC, product_count DESC LIMIT ?",
        [limit],
    )


def _price_comparison(product):
    """Compare farmer's price to latest mandi modal price for same commodity."""
    row = db.query_one(
        "SELECT * FROM market_prices WHERE LOWER(commodity)=LOWER(?) "
        "ORDER BY arrival_date DESC LIMIT 1", [product["name"]]
    )
    if not row or not row.get("modal_price"):
        return None
    try:
        farmer_price = float(product["price"])
        modal = float(row["modal_price"])
    except (TypeError, ValueError):
        return None
    diff = farmer_price - modal
    return {
        "modal_price": modal,
        "market": row["market"],
        "arrival_date": row["arrival_date"],
        "source": row.get("source"),
        "diff": diff,
        "direction": "below" if diff < 0 else ("above" if diff > 0 else "equal"),
        "abs_diff": abs(diff),
    }
