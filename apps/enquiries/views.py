"""Enquiry + negotiation views for buyers and farmers."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from core import db
from core.http import forbidden, not_found, redirect
from core.views import add_message, login_required, render, role_required
from apps.accounts.models import get_buyer_by_user, get_farmer, get_farmer_by_user
from apps.notifications.models import notify
from apps.products import models as pmodels

from . import models


# --- Buyer: create an enquiry (and open a negotiation) ----------------------
@role_required("buyer")
def create_enquiry(request):
    product_id = request.POST("product_id")
    product = pmodels.get_product(product_id)
    if not product or product["status"] == "deleted":
        return not_found("Product not found")
    buyer = get_buyer_by_user(request.user["id"])

    try:
        qty = Decimal(str(request.POST("required_qty") or product["min_order_qty"]))
        price = Decimal(str(request.POST("proposed_price") or product["price"]))
    except (InvalidOperation, ValueError):
        add_message(request, "error", "Enter valid quantity and price.")
        return redirect(f"/products/{product_id}")

    is_advance = product["listing_type"] == "upcoming_harvest"
    eid = models.create_enquiry(
        product_id=product_id, buyer_id=buyer["id"], farmer_id=product["farmer_id"],
        required_qty=qty, delivery_district=request.POST("delivery_district"),
        expected_date=request.POST("expected_date") or None,
        message=request.POST("message"), is_advance=is_advance,
    )
    pmodels.increment_enquiries(product_id)

    # open a negotiation with the buyer's opening offer
    neg_id = models.get_or_create_negotiation(
        product_id=product_id, buyer_id=buyer["id"],
        farmer_id=product["farmer_id"], enquiry_id=eid,
    )
    models.create_offer(
        negotiation_id=neg_id, product_id=product_id, made_by="buyer",
        offered_qty=qty, offered_price=price, unit=product["unit"],
        message=request.POST("message"),
    )

    farmer = get_farmer(product["farmer_id"])
    notify(farmer["user_id"], "enquiry", "New enquiry received",
           f"{request.user['full_name']} enquired about {product['name']} "
           f"({qty} {product['unit']} @ ₹{price}).", f"/negotiations/{neg_id}")

    add_message(request, "success",
                "Enquiry sent! You can negotiate in your Negotiations area.")
    return redirect(f"/negotiations/{neg_id}")


# --- Negotiation thread (both parties) --------------------------------------
@login_required
def negotiation_detail(request, id):
    neg = models.get_negotiation(id)
    if not neg:
        return not_found()
    role, me = _party(request, neg)
    if role is None:
        return forbidden("You are not part of this negotiation.")

    product = pmodels.get_product(neg["product_id"])
    offer_rows = models.offers_for_negotiation(id)
    for o in offer_rows:
        o["is_mine"] = o["made_by"] == role
        try:
            o["line_total"] = Decimal(str(o["offered_qty"])) * Decimal(str(o["offered_price"]))
        except (InvalidOperation, ValueError):
            o["line_total"] = 0
    latest = offer_rows[-1] if offer_rows else None
    # can I act on the latest offer? Only if it was made by the OTHER party and pending.
    can_respond = bool(latest and latest["status"] == "pending" and latest["made_by"] != role)
    inv = pmodels.get_inventory(neg["product_id"])

    return render(request, "enquiries/negotiation_detail.html", {
        "negotiation": neg, "product": product, "offers": offer_rows,
        "latest": latest, "role": role, "can_respond": can_respond,
        "inventory": inv, "is_open": neg["is_open"],
        "farmer": get_farmer(neg["farmer_id"]),
    })


@login_required
def respond_offer(request, id):
    """Counter / accept / reject the latest pending offer."""
    neg = models.get_negotiation(id)
    if not neg:
        return not_found()
    role, me = _party(request, neg)
    if role is None:
        return forbidden()

    action = request.POST("action")
    latest = models.latest_offer(id)
    product = pmodels.get_product(neg["product_id"])

    if not neg["is_open"]:
        add_message(request, "error", "This negotiation is closed.")
        return redirect(f"/negotiations/{id}")

    if action == "counter":
        try:
            qty = Decimal(str(request.POST("offered_qty")))
            price = Decimal(str(request.POST("offered_price")))
            if qty <= 0 or price < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            add_message(request, "error", "Enter a valid quantity and price.")
            return redirect(f"/negotiations/{id}")
        models.create_offer(
            negotiation_id=id, product_id=neg["product_id"], made_by=role,
            offered_qty=qty, offered_price=price, unit=product["unit"],
            message=request.POST("message"),
        )
        _notify_counterparty(request, neg, role, "counteroffer",
                             "New counteroffer", f"on {product['name']}", id)
        add_message(request, "success", "Counteroffer sent.")

    elif action == "accept":
        if not latest or latest["status"] != "pending" or latest["made_by"] == role:
            add_message(request, "error", "There is no offer from the other party to accept.")
            return redirect(f"/negotiations/{id}")
        models.set_offer_status(latest["id"], "accepted")
        if neg.get("enquiry_id"):
            models.set_enquiry_status(neg["enquiry_id"], "converted")
        _notify_counterparty(request, neg, role, "order_accepted",
                             "Offer accepted", f"on {product['name']}", id)
        add_message(request, "success",
                    "Offer accepted! You can now convert it into an order.")
        return redirect(f"/negotiations/{id}")

    elif action == "reject":
        if latest and latest["status"] == "pending":
            models.set_offer_status(latest["id"], "rejected")
        models.close_negotiation(id)
        _notify_counterparty(request, neg, role, "order_cancelled",
                             "Offer rejected", f"on {product['name']}", id)
        add_message(request, "info", "Offer rejected and negotiation closed.")

    return redirect(f"/negotiations/{id}")


# --- Lists ------------------------------------------------------------------
@role_required("farmer")
def farmer_enquiries(request):
    farmer = get_farmer_by_user(request.user["id"])
    rows = models.enquiries_for_farmer(farmer["id"])
    return render(request, "enquiries/farmer_enquiries.html", {"enquiries": rows})


@role_required("farmer")
def farmer_negotiations(request):
    farmer = get_farmer_by_user(request.user["id"])
    rows = models.negotiations_for_farmer(farmer["id"])
    return render(request, "enquiries/negotiation_list.html",
                  {"negotiations": rows, "role": "farmer"})


@role_required("buyer")
def buyer_enquiries(request):
    buyer = get_buyer_by_user(request.user["id"])
    rows = models.enquiries_for_buyer(buyer["id"])
    return render(request, "enquiries/buyer_enquiries.html", {"enquiries": rows})


@role_required("buyer")
def buyer_negotiations(request):
    buyer = get_buyer_by_user(request.user["id"])
    rows = models.negotiations_for_buyer(buyer["id"])
    return render(request, "enquiries/negotiation_list.html",
                  {"negotiations": rows, "role": "buyer"})


# --- helpers ----------------------------------------------------------------
def _party(request, neg):
    """Return (role, profile) where role in {'buyer','farmer'} if the current
    user belongs to this negotiation, else (None, None)."""
    if request.user["role"] == "buyer":
        bp = get_buyer_by_user(request.user["id"])
        if bp and bp["id"] == neg["buyer_id"]:
            return "buyer", bp
    elif request.user["role"] == "farmer":
        fp = get_farmer_by_user(request.user["id"])
        if fp and fp["id"] == neg["farmer_id"]:
            return "farmer", fp
    return None, None


def _notify_counterparty(request, neg, role, ntype, title, suffix, neg_id):
    if role == "buyer":
        farmer = get_farmer(neg["farmer_id"])
        target_user = farmer["user_id"]
    else:
        bp = db.query_one("SELECT user_id FROM buyer_profiles WHERE id=?", [neg["buyer_id"]])
        target_user = bp["user_id"] if bp else None
    if target_user:
        notify(target_user, ntype, title,
               f"{request.user['full_name']} {suffix}.", f"/negotiations/{neg_id}")
