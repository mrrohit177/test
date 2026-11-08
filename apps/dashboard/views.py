"""Role-aware dashboards: router entry + farmer/buyer/admin dashboards."""
from __future__ import annotations

from decimal import Decimal

from core import db
from core.http import redirect
from core.views import add_message, login_required, render, role_required
from apps.accounts.models import get_buyer_by_user, get_farmer_by_user
from apps.notifications.models import unread_count


@login_required
def dashboard_home(request):
    role = request.user["role"]
    if role == "farmer":
        return farmer_dashboard(request)
    if role == "buyer":
        return buyer_dashboard(request)
    if role == "admin":
        return redirect("/admin")
    add_message(request, "error", "Unknown role.")
    return redirect("/")


# --- Farmer dashboard -------------------------------------------------------
def farmer_dashboard(request):
    farmer = get_farmer_by_user(request.user["id"])
    fid = farmer["id"]

    def one(sql, params=()):
        row = db.query_one(sql, params)
        return list(row.values())[0] if row else 0

    total_products = one("SELECT COUNT(*) FROM products WHERE farmer_id=? AND status!='deleted'", [fid])
    active = one("SELECT COUNT(*) FROM products WHERE farmer_id=? AND status='active'", [fid])
    stock = one("SELECT COALESCE(SUM(CAST(inv.available_qty AS REAL)),0) FROM product_inventory inv "
                "JOIN products p ON p.id=inv.product_id WHERE p.farmer_id=? AND p.status!='deleted'", [fid])
    enquiries = one("SELECT COUNT(*) FROM enquiries WHERE farmer_id=?", [fid])
    pending_orders = one("SELECT COUNT(*) FROM orders WHERE farmer_id=? AND status='pending'", [fid])
    confirmed = one("SELECT COUNT(*) FROM orders WHERE farmer_id=? AND status IN ('accepted','confirmed','dispatched','ready_for_pickup','delivered')", [fid])
    completed = one("SELECT COUNT(*) FROM orders WHERE farmer_id=? AND status='completed'", [fid])
    revenue = one("SELECT COALESCE(SUM(CAST(total_amount AS REAL)),0) FROM orders WHERE farmer_id=? AND status='completed'", [fid])

    recent_orders = db.query(
        "SELECT o.*, u.full_name AS buyer_name FROM orders o "
        "JOIN buyer_profiles bp ON bp.id=o.buyer_id JOIN users u ON u.id=bp.user_id "
        "WHERE o.farmer_id=? ORDER BY o.created_at DESC LIMIT 5", [fid])
    recent_enquiries = db.query(
        "SELECT e.*, p.name AS product_name, u.full_name AS buyer_name FROM enquiries e "
        "JOIN products p ON p.id=e.product_id JOIN buyer_profiles bp ON bp.id=e.buyer_id "
        "JOIN users u ON u.id=bp.user_id WHERE e.farmer_id=? ORDER BY e.created_at DESC LIMIT 5", [fid])
    low_stock = db.query(
        "SELECT p.name, p.unit, inv.available_qty FROM product_inventory inv "
        "JOIN products p ON p.id=inv.product_id WHERE p.farmer_id=? AND p.status='active' "
        "AND CAST(inv.available_qty AS REAL) <= CAST(inv.low_stock_threshold AS REAL) "
        "AND CAST(inv.low_stock_threshold AS REAL) > 0 LIMIT 5", [fid])

    return render(request, "dashboard/farmer_dashboard.html", {
        "farmer": farmer,
        "active_nav": "dashboard",
        "unread": unread_count(request.user["id"]),
        "stats": {
            "total_products": total_products, "active": active,
            "stock": round(stock, 2), "enquiries": enquiries,
            "pending_orders": pending_orders, "confirmed": confirmed,
            "completed": completed, "revenue": round(revenue, 2),
        },
        "recent_orders": recent_orders,
        "recent_enquiries": recent_enquiries,
        "low_stock": low_stock,
    })


# --- Buyer dashboard --------------------------------------------------------
def buyer_dashboard(request):
    buyer = get_buyer_by_user(request.user["id"])
    bid = buyer["id"]

    def one(sql, params=()):
        row = db.query_one(sql, params)
        return list(row.values())[0] if row else 0

    total_enquiries = one("SELECT COUNT(*) FROM enquiries WHERE buyer_id=?", [bid])
    active_orders = one("SELECT COUNT(*) FROM orders WHERE buyer_id=? AND status IN ('pending','accepted','confirmed','dispatched','ready_for_pickup','delivered')", [bid])
    pending = one("SELECT COUNT(*) FROM orders WHERE buyer_id=? AND status='pending'", [bid])
    completed = one("SELECT COUNT(*) FROM orders WHERE buyer_id=? AND status='completed'", [bid])
    saved = one("SELECT COUNT(*) FROM wishlists WHERE buyer_id=?", [bid])
    negotiations = one("SELECT COUNT(*) FROM negotiations WHERE buyer_id=? AND is_open=1", [bid])

    recent_orders = db.query(
        "SELECT o.*, f.display_name AS farmer_name FROM orders o "
        "JOIN farmer_profiles f ON f.id=o.farmer_id WHERE o.buyer_id=? "
        "ORDER BY o.created_at DESC LIMIT 5", [bid])
    wishlist = db.query(
        "SELECT w.*, p.name, p.price, p.unit FROM wishlists w JOIN products p ON p.id=w.product_id "
        "WHERE w.buyer_id=? ORDER BY w.created_at DESC LIMIT 6", [bid])

    return render(request, "dashboard/buyer_dashboard.html", {
        "buyer": buyer,
        "active_nav": "dashboard",
        "unread": unread_count(request.user["id"]),
        "stats": {
            "enquiries": total_enquiries, "active_orders": active_orders,
            "pending": pending, "completed": completed,
            "saved": saved, "negotiations": negotiations,
        },
        "recent_orders": recent_orders,
        "wishlist": wishlist,
    })


# --- Farmer: sales history --------------------------------------------------
@role_required("farmer")
def sales_history(request):
    farmer = get_farmer_by_user(request.user["id"])
    rows = db.query(
        "SELECT o.*, u.full_name AS buyer_name FROM orders o "
        "JOIN buyer_profiles bp ON bp.id=o.buyer_id JOIN users u ON u.id=bp.user_id "
        "WHERE o.farmer_id=? AND o.status='completed' ORDER BY o.completed_at DESC", [farmer["id"]])
    total = sum(Decimal(str(r["total_amount"])) for r in rows) if rows else Decimal("0")
    return render(request, "dashboard/sales_history.html", {
        "orders": rows, "total": total, "active_nav": "sales",
        "unread": unread_count(request.user["id"]), "farmer": farmer,
    })


# --- Buyer: purchase history ------------------------------------------------
@role_required("buyer")
def purchase_history(request):
    buyer = get_buyer_by_user(request.user["id"])
    rows = db.query(
        "SELECT o.*, f.display_name AS farmer_name FROM orders o "
        "JOIN farmer_profiles f ON f.id=o.farmer_id WHERE o.buyer_id=? AND o.status='completed' "
        "ORDER BY o.completed_at DESC", [buyer["id"]])
    return render(request, "dashboard/purchase_history.html", {
        "orders": rows, "active_nav": "history",
        "unread": unread_count(request.user["id"]), "buyer": buyer,
    })


# --- Buyer: wishlist + favourite farmers -----------------------------------
@role_required("buyer")
def wishlist(request):
    buyer = get_buyer_by_user(request.user["id"])
    if request.method == "POST":
        action = request.POST("action")
        product_id = request.POST("product_id")
        if action == "add":
            try:
                db.execute("INSERT OR IGNORE INTO wishlists (id, buyer_id, product_id) VALUES (?,?,?)",
                           [db.new_uuid(), buyer["id"], product_id])
                add_message(request, "success", "Added to wishlist.")
            except Exception:
                pass
        elif action == "remove":
            db.execute("DELETE FROM wishlists WHERE buyer_id=? AND product_id=?", [buyer["id"], product_id])
            add_message(request, "success", "Removed from wishlist.")
        return redirect(request.POST("next") or "/buyer/wishlist")

    rows = db.query(
        "SELECT w.*, p.name, p.price, p.unit, p.status, f.display_name AS farmer_name, "
        "(SELECT path FROM product_images pi WHERE pi.product_id=p.id ORDER BY pi.is_primary DESC LIMIT 1) AS image_path "
        "FROM wishlists w JOIN products p ON p.id=w.product_id "
        "JOIN farmer_profiles f ON f.id=p.farmer_id WHERE w.buyer_id=? ORDER BY w.created_at DESC",
        [buyer["id"]])
    return render(request, "dashboard/wishlist.html", {
        "items": rows, "active_nav": "wishlist",
        "unread": unread_count(request.user["id"]), "buyer": buyer,
    })
