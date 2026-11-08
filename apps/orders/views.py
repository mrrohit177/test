"""Order views: create from accepted offer / direct, lifecycle, lists, detail."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from core import db
from core.http import forbidden, not_found, redirect
from core.views import add_message, login_required, render, role_required
from apps.accounts.models import get_buyer_by_user, get_farmer, get_farmer_by_user
from apps.enquiries import models as emodels
from apps.notifications.models import notify
from apps.products import models as pmodels

from . import models


# --- Create order from an accepted negotiation offer ------------------------
@role_required("buyer")
def create_from_offer(request):
    neg_id = request.POST("negotiation_id")
    neg = emodels.get_negotiation(neg_id)
    if not neg:
        return not_found()
    buyer = get_buyer_by_user(request.user["id"])
    if not buyer or buyer["id"] != neg["buyer_id"]:
        return forbidden()
    offer = emodels.latest_offer(neg_id)
    if not offer or offer["status"] != "accepted":
        add_message(request, "error", "No accepted offer to convert into an order.")
        return redirect(f"/negotiations/{neg_id}")

    product = pmodels.get_product(neg["product_id"])
    fulfilment = request.POST("fulfilment_method", "pickup")
    try:
        oid, number = models.create_order(
            buyer_id=buyer["id"], farmer_id=neg["farmer_id"], product=product,
            quantity=offer["offered_qty"], unit_price=offer["offered_price"],
            fulfilment_method=fulfilment, accepted_offer_id=offer["id"],
            notes=request.POST("notes"),
        )
    except pmodels.InventoryError as e:
        add_message(request, "error", f"Could not create order: {e}")
        return redirect(f"/negotiations/{neg_id}")

    emodels.close_negotiation(neg_id)
    farmer = get_farmer(neg["farmer_id"])
    notify(farmer["user_id"], "order", "New order received",
           f"Order {number} for {offer['offered_qty']} {product['unit']} of {product['name']}.",
           f"/orders/{oid}")
    add_message(request, "success", f"Order {number} placed! Awaiting farmer confirmation.")
    return redirect(f"/orders/{oid}")


# --- Direct order (retail quick buy, no negotiation) ------------------------
@role_required("buyer")
def create_direct(request):
    product_id = request.POST("product_id")
    product = pmodels.get_product(product_id)
    if not product or product["status"] != "active":
        return not_found("Product unavailable")
    buyer = get_buyer_by_user(request.user["id"])
    try:
        qty = Decimal(str(request.POST("quantity")))
        min_qty = Decimal(str(product["min_order_qty"]))
        if qty < min_qty:
            add_message(request, "error", f"Minimum order is {min_qty} {product['unit']}.")
            return redirect(f"/products/{product_id}")
    except (InvalidOperation, ValueError):
        add_message(request, "error", "Enter a valid quantity.")
        return redirect(f"/products/{product_id}")

    try:
        oid, number = models.create_order(
            buyer_id=buyer["id"], farmer_id=product["farmer_id"], product=product,
            quantity=qty, unit_price=product["price"],
            fulfilment_method=request.POST("fulfilment_method", "pickup"),
        )
    except pmodels.InventoryError as e:
        add_message(request, "error", f"Could not place order: {e}")
        return redirect(f"/products/{product_id}")

    farmer = get_farmer(product["farmer_id"])
    notify(farmer["user_id"], "order", "New order received",
           f"Order {number} for {qty} {product['unit']} of {product['name']}.",
           f"/orders/{oid}")
    add_message(request, "success", f"Order {number} placed! Awaiting farmer confirmation.")
    return redirect(f"/orders/{oid}")


# --- Order detail -----------------------------------------------------------
@login_required
def order_detail(request, id):
    order = models.get_order_full(id)
    if not order:
        return not_found()
    role = _role_for_order(request, order)
    if role is None:
        return forbidden("You cannot view this order.")
    next_states = models.TRANSITIONS.get(order["status"], [])
    return render(request, "orders/order_detail.html", {
        "order": order, "role": role, "next_states": next_states,
        "status_labels": models.STATUS_LABELS,
    })


# --- Lifecycle transition ---------------------------------------------------
@login_required
def update_status(request, id):
    order = models.get_order(id)
    if not order:
        return not_found()
    role = _role_for_order(request, order)
    if role is None:
        return forbidden()

    new_status = request.POST("status")

    # Permission matrix: farmers drive fulfilment; buyers can confirm receipt/cancel pending.
    farmer_actions = {"accepted", "rejected", "confirmed", "ready_for_pickup", "dispatched"}
    buyer_actions = {"completed", "cancelled"}  # buyer confirms receipt / cancels while pending

    if role == "farmer" and new_status not in farmer_actions:
        return forbidden("Farmers cannot set this status.")
    if role == "buyer":
        if new_status == "cancelled" and order["status"] not in ("pending", "accepted"):
            add_message(request, "error", "You can only cancel before the order is confirmed.")
            return redirect(f"/orders/{id}")
        if new_status == "completed" and order["status"] not in ("delivered", "ready_for_pickup", "dispatched"):
            add_message(request, "error", "You can confirm receipt once the order is ready or dispatched.")
            return redirect(f"/orders/{id}")
        if new_status not in buyer_actions:
            return forbidden("Buyers cannot set this status.")

    try:
        models.transition(id, new_status, actor_role=role)
    except models.OrderError as e:
        add_message(request, "error", str(e))
        return redirect(f"/orders/{id}")

    # notify the other party
    _notify_other(request, order, role, new_status)
    add_message(request, "success", f"Order marked {models.STATUS_LABELS.get(new_status, new_status)}.")
    return redirect(f"/orders/{id}")


# --- Lists ------------------------------------------------------------------
@role_required("farmer")
def farmer_orders(request):
    farmer = get_farmer_by_user(request.user["id"])
    status = request.GET("status")
    rows = models.orders_for_farmer(farmer["id"], status=status)
    return render(request, "orders/farmer_orders.html", {"orders": rows, "status": status})


@role_required("buyer")
def buyer_orders(request):
    buyer = get_buyer_by_user(request.user["id"])
    rows = models.orders_for_buyer(buyer["id"])
    return render(request, "orders/buyer_orders.html", {"orders": rows})


# --- helpers ----------------------------------------------------------------
def _role_for_order(request, order):
    if request.user["role"] == "farmer":
        fp = get_farmer_by_user(request.user["id"])
        if fp and fp["id"] == order["farmer_id"]:
            return "farmer"
    elif request.user["role"] == "buyer":
        bp = get_buyer_by_user(request.user["id"])
        if bp and bp["id"] == order["buyer_id"]:
            return "buyer"
    elif request.user["role"] == "admin":
        return "admin"
    return None


def _notify_other(request, order, role, new_status):
    label = models.STATUS_LABELS.get(new_status, new_status)
    if role == "farmer":
        bp = db.query_one("SELECT user_id FROM buyer_profiles WHERE id=?", [order["buyer_id"]])
        target = bp["user_id"] if bp else None
    else:
        farmer = get_farmer(order["farmer_id"])
        target = farmer["user_id"] if farmer else None
    if target:
        notify(target, "delivery_status" if new_status in
               ("ready_for_pickup", "dispatched", "delivered") else "order",
               f"Order {order['order_number']}: {label}",
               f"The order status is now {label}.", f"/orders/{order['id']}")
