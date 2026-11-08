"""Custom admin dashboard (separate from any superuser tooling)."""
from __future__ import annotations

import csv
import io

from core import db
from core.http import Response, redirect
from core.views import add_message, render, role_required
from apps.accounts.models import get_farmer, update_farmer


@role_required("admin")
def admin_home(request):
    def one(sql):
        row = db.query_one(sql)
        return list(row.values())[0] if row else 0

    stats = {
        "farmers": one("SELECT COUNT(*) FROM users WHERE role='farmer'"),
        "buyers": one("SELECT COUNT(*) FROM users WHERE role='buyer'"),
        "verified_farmers": one("SELECT COUNT(*) FROM farmer_profiles WHERE verification_level IN ('identity_verified','farm_verified')"),
        "products": one("SELECT COUNT(*) FROM products WHERE status!='deleted'"),
        "active": one("SELECT COUNT(*) FROM products WHERE status='active'"),
        "orders": one("SELECT COUNT(*) FROM orders"),
        "pending_orders": one("SELECT COUNT(*) FROM orders WHERE status='pending'"),
        "completed_orders": one("SELECT COUNT(*) FROM orders WHERE status='completed'"),
        "enquiries": one("SELECT COUNT(*) FROM enquiries"),
        "disputes": one("SELECT COUNT(*) FROM complaints WHERE status IN ('open','investigating')"),
        "revenue": round(one("SELECT COALESCE(SUM(CAST(total_amount AS REAL)),0) FROM orders WHERE status='completed'"), 2),
    }
    recent_orders = db.query(
        "SELECT o.*, f.display_name AS farmer_name, u.full_name AS buyer_name FROM orders o "
        "JOIN farmer_profiles f ON f.id=o.farmer_id JOIN buyer_profiles bp ON bp.id=o.buyer_id "
        "JOIN users u ON u.id=bp.user_id ORDER BY o.created_at DESC LIMIT 8")
    districts = db.query(
        "SELECT district, COUNT(*) AS n FROM farmer_profiles GROUP BY district ORDER BY n DESC LIMIT 10")
    top_products = db.query(
        "SELECT p.name, COUNT(oi.id) AS orders FROM order_items oi "
        "JOIN products p ON p.id=oi.product_id GROUP BY p.name ORDER BY orders DESC LIMIT 8")
    return render(request, "admin/dashboard.html", {
        "stats": stats, "recent_orders": recent_orders,
        "districts": districts, "top_products": top_products,
        "active_nav": "overview",
    })


@role_required("admin")
def admin_farmers(request):
    rows = db.query(
        "SELECT f.*, u.full_name, u.mobile, u.created_at AS joined, "
        "(SELECT COUNT(*) FROM products p WHERE p.farmer_id=f.id AND p.status!='deleted') AS product_count "
        "FROM farmer_profiles f JOIN users u ON u.id=f.user_id ORDER BY u.created_at DESC")
    return render(request, "admin/farmers.html", {"farmers": rows, "active_nav": "farmers"})


@role_required("admin")
def admin_verify(request, farmer_id):
    farmer = get_farmer(farmer_id)
    if not farmer:
        add_message(request, "error", "Farmer not found.")
        return redirect("/admin/farmers")
    level = request.POST("verification_level")
    if level in ("basic", "mobile_verified", "identity_verified", "farm_verified"):
        update_farmer(farmer_id, verification_level=level)
        from apps.accounts.models import log_action
        log_action(request.user["id"], "verify_farmer", entity="farmer_profile",
                   entity_id=farmer_id, detail=level)
        add_message(request, "success", f"Verification set to {level.replace('_', ' ')}.")
    return redirect("/admin/farmers")


@role_required("admin")
def admin_buyers(request):
    rows = db.query(
        "SELECT bp.*, u.full_name, u.mobile, u.created_at AS joined FROM buyer_profiles bp "
        "JOIN users u ON u.id=bp.user_id ORDER BY u.created_at DESC")
    return render(request, "admin/buyers.html", {"buyers": rows, "active_nav": "buyers"})


@role_required("admin")
def admin_products(request):
    rows = db.query(
        "SELECT p.*, f.display_name AS farmer_name FROM products p "
        "JOIN farmer_profiles f ON f.id=p.farmer_id WHERE p.status!='deleted' "
        "ORDER BY p.created_at DESC LIMIT 200")
    return render(request, "admin/products.html", {"products": rows, "active_nav": "products"})


@role_required("admin")
def admin_product_action(request, id):
    action = request.POST("action")
    if action == "remove":
        db.execute("UPDATE products SET status='deleted' WHERE id=?", [id])
        add_message(request, "success", "Product removed.")
    elif action == "reinstate":
        db.execute("UPDATE products SET status='active' WHERE id=?", [id])
        add_message(request, "success", "Product reinstated.")
    return redirect("/admin/products")


@role_required("admin")
def admin_orders(request):
    rows = db.query(
        "SELECT o.*, f.display_name AS farmer_name, u.full_name AS buyer_name FROM orders o "
        "JOIN farmer_profiles f ON f.id=o.farmer_id JOIN buyer_profiles bp ON bp.id=o.buyer_id "
        "JOIN users u ON u.id=bp.user_id ORDER BY o.created_at DESC LIMIT 200")
    from apps.orders.models import STATUS_LABELS
    for r in rows:
        r["status_label"] = STATUS_LABELS.get(r["status"], r["status"])
    return render(request, "admin/orders.html", {"orders": rows, "active_nav": "orders"})


@role_required("admin")
def admin_complaints(request):
    if request.method == "POST":
        cid = request.POST("complaint_id")
        status = request.POST("status")
        if status in ("open", "investigating", "resolved", "dismissed"):
            db.execute("UPDATE complaints SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", [status, cid])
            add_message(request, "success", "Complaint updated.")
        return redirect("/admin/complaints")
    rows = db.query(
        "SELECT c.*, u.full_name AS raised_by_name FROM complaints c "
        "JOIN users u ON u.id=c.raised_by ORDER BY c.created_at DESC")
    return render(request, "admin/complaints.html", {"complaints": rows, "active_nav": "complaints"})


@role_required("admin")
def admin_reports(request):
    """CSV export of completed orders."""
    kind = request.GET("export")
    if kind == "orders":
        rows = db.query(
            "SELECT o.order_number, o.status, o.total_amount, o.created_at, "
            "f.display_name AS farmer, u.full_name AS buyer FROM orders o "
            "JOIN farmer_profiles f ON f.id=o.farmer_id JOIN buyer_profiles bp ON bp.id=o.buyer_id "
            "JOIN users u ON u.id=bp.user_id ORDER BY o.created_at DESC")
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["order_number", "status", "total_amount",
                                                 "created_at", "farmer", "buyer"])
        writer.writeheader()
        writer.writerows(rows)
        return Response(buf.getvalue(), content_type="text/csv; charset=utf-8",
                        headers=[("Content-Disposition", "attachment; filename=orders.csv")])

    district_report = db.query(
        "SELECT district, COUNT(*) AS farmers FROM farmer_profiles GROUP BY district ORDER BY farmers DESC")
    product_report = db.query(
        "SELECT p.name, COUNT(oi.id) AS times_ordered, "
        "COALESCE(SUM(CAST(oi.line_total AS REAL)),0) AS value FROM order_items oi "
        "JOIN products p ON p.id=oi.product_id GROUP BY p.name ORDER BY times_ordered DESC LIMIT 20")
    return render(request, "admin/reports.html", {
        "district_report": district_report, "product_report": product_report,
        "active_nav": "reports",
    })
