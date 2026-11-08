"""Transport coordination module (MVP: record transport requests)."""
from __future__ import annotations

from core import db
from core.http import redirect
from core.views import add_message, login_required, render

requests_tbl = db.Table("transport_requests")


@login_required
def transport_list(request):
    rows = requests_tbl.filter({"requested_by": request.user["id"]}, order_by="created_at DESC")
    active_nav = "transport"
    unread = _unread(request)
    return render(request, "logistics/transport_list.html", {
        "requests": rows, "active_nav": active_nav, "unread": unread,
        "role": request.user["role"],
    })


@login_required
def transport_create(request):
    if request.method == "POST":
        order_id = request.POST("order_id") or None
        requests_tbl.insert(
            order_id=order_id, requested_by=request.user["id"],
            pickup_district=request.POST("pickup_district", ""),
            pickup_location=request.POST("pickup_location"),
            delivery_district=request.POST("delivery_district", ""),
            delivery_location=request.POST("delivery_location"),
            product_type=request.POST("product_type"),
            quantity=request.POST("quantity") or None,
            unit=request.POST("unit") or None,
            estimated_weight_kg=request.POST("estimated_weight_kg") or None,
            vehicle_requirement=request.POST("vehicle_requirement"),
            preferred_date=request.POST("preferred_date") or None,
            status="open",
        )
        add_message(request, "success",
                    "Transport request recorded. Transport-partner quotations are coming soon.")
        return redirect("/transport")
    return render(request, "logistics/transport_form.html", {
        "active_nav": "transport", "unread": _unread(request),
        "role": request.user["role"],
    })


def _unread(request):
    from apps.notifications.models import unread_count
    return unread_count(request.user["id"])
