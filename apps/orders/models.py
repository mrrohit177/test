"""Order data access + lifecycle + inventory reservation service."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from core import db
from apps.products import models as pmodels

orders = db.Table("orders")
order_items = db.Table("order_items")

# status -> allowed next statuses (farmer-driven unless noted)
TRANSITIONS = {
    "pending": ["accepted", "rejected", "cancelled"],
    "accepted": ["confirmed", "cancelled"],
    "confirmed": ["ready_for_pickup", "dispatched", "cancelled"],
    "ready_for_pickup": ["dispatched", "delivered", "completed", "cancelled"],
    "dispatched": ["delivered", "completed", "cancelled"],
    "delivered": ["completed"],
    "completed": [],
    "rejected": [],
    "cancelled": [],
}

STATUS_LABELS = {
    "draft": "Draft", "pending": "Pending", "accepted": "Accepted",
    "rejected": "Rejected", "negotiation": "Negotiation", "confirmed": "Confirmed",
    "ready_for_pickup": "Ready for Pickup", "dispatched": "Dispatched",
    "delivered": "Delivered", "completed": "Completed", "cancelled": "Cancelled",
    "disputed": "Disputed",
}

# statuses that hold a stock reservation
RESERVED_STATES = {"accepted", "confirmed", "ready_for_pickup", "dispatched", "delivered"}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _order_number():
    row = db.query_one("SELECT COUNT(*) AS c FROM orders")
    seq = (row["c"] if row else 0) + 1000
    return f"FC-{datetime.now(timezone.utc).strftime('%Y%m')}-{seq:06d}"


def create_order(*, buyer_id, farmer_id, product, quantity, unit_price,
                 fulfilment_method="pickup", accepted_offer_id=None,
                 parent_checkout_ref=None, platform_fee_pct=Decimal("0"),
                 notes=None):
    """Create a pending order and reserve stock atomically.

    Reserving stock here means a confirmed negotiation becomes a real hold on
    inventory. Raises pmodels.InventoryError if stock is insufficient.
    """
    quantity = Decimal(str(quantity))
    unit_price = Decimal(str(unit_price))
    product_amount = (quantity * unit_price).quantize(Decimal("0.01"))
    platform_fee = (product_amount * Decimal(str(platform_fee_pct)) / 100).quantize(Decimal("0.01"))
    total = product_amount + platform_fee

    order_number = _order_number()
    oid = orders.insert(
        order_number=order_number,
        parent_checkout_ref=parent_checkout_ref,
        buyer_id=buyer_id, farmer_id=farmer_id,
        accepted_offer_id=accepted_offer_id,
        status="pending", fulfilment_method=fulfilment_method,
        product_amount=str(product_amount), platform_fee=str(platform_fee),
        transport_amount="0", tax_amount="0", total_amount=str(total),
        payment_status="pending", payment_method="cash_on_delivery",
        notes=notes, created_at=_now(), updated_at=_now(),
    )
    order_items.insert(
        order_id=oid, product_id=product["id"], product_name=product["name"],
        unit=product["unit"], quantity=str(quantity), unit_price=str(unit_price),
        line_total=str(product_amount),
    )
    # reserve stock (atomic; raises on insufficient)
    pmodels.reserve_stock(product["id"], quantity, reference=oid)
    return oid, order_number


def get_order(order_id):
    return orders.get(id=order_id)


def get_order_full(order_id):
    o = db.query_one(
        "SELECT o.*, f.display_name AS farmer_name, f.district AS farmer_district, "
        "fu.full_name AS farmer_contact_name, "
        "bu.full_name AS buyer_name, bp.business_name AS buyer_business "
        "FROM orders o "
        "JOIN farmer_profiles f ON f.id=o.farmer_id "
        "JOIN users fu ON fu.id=f.user_id "
        "JOIN buyer_profiles bp ON bp.id=o.buyer_id "
        "JOIN users bu ON bu.id=bp.user_id WHERE o.id=?", [order_id])
    if not o:
        return None
    o["items"] = order_items.filter({"order_id": order_id})
    o["status_label"] = STATUS_LABELS.get(o["status"], o["status"])
    return o


def items_for(order_id):
    return order_items.filter({"order_id": order_id})


def orders_for_farmer(farmer_id, *, status=None):
    where = {"farmer_id": farmer_id}
    if status:
        where["status"] = status
    rows = db.query(
        "SELECT o.*, u.full_name AS buyer_name FROM orders o "
        "JOIN buyer_profiles bp ON bp.id=o.buyer_id JOIN users u ON u.id=bp.user_id "
        "WHERE o.farmer_id=? ORDER BY o.created_at DESC", [farmer_id])
    if status:
        rows = [r for r in rows if r["status"] == status]
    for r in rows:
        r["status_label"] = STATUS_LABELS.get(r["status"], r["status"])
    return rows


def orders_for_buyer(buyer_id):
    rows = db.query(
        "SELECT o.*, f.display_name AS farmer_name FROM orders o "
        "JOIN farmer_profiles f ON f.id=o.farmer_id "
        "WHERE o.buyer_id=? ORDER BY o.created_at DESC", [buyer_id])
    for r in rows:
        r["status_label"] = STATUS_LABELS.get(r["status"], r["status"])
    return rows


class OrderError(Exception):
    pass


def transition(order_id, new_status, *, actor_role):
    """Move an order through its lifecycle, managing stock reservation/commit."""
    order = get_order(order_id)
    if not order:
        raise OrderError("Order not found")
    current = order["status"]
    allowed = TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise OrderError(f"Cannot move order from '{current}' to '{new_status}'.")

    items = items_for(order_id)
    updates = {"status": new_status, "updated_at": _now()}

    if new_status == "confirmed":
        updates["confirmed_at"] = _now()
    elif new_status == "completed":
        updates["completed_at"] = _now()
        updates["payment_status"] = "paid"
        # commit reserved stock -> sold
        for it in items:
            pmodels.commit_sale(it["product_id"], Decimal(str(it["quantity"])), reference=order_id)
    elif new_status in ("cancelled", "rejected"):
        updates["cancelled_at"] = _now()
        # release reservation only if currently holding one
        if current in RESERVED_STATES or current == "pending":
            for it in items:
                try:
                    pmodels.release_stock(it["product_id"], Decimal(str(it["quantity"])), reference=order_id)
                except pmodels.InventoryError:
                    pass

    orders.update({"id": order_id}, **updates)
    return new_status


def set_payment(order_id, *, status, method=None, reference=None):
    fields = {"payment_status": status, "updated_at": _now()}
    if method:
        fields["payment_method"] = method
    orders.update({"id": order_id}, **fields)
