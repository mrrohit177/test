"""Enquiries, negotiations, and offers data access."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import db

enquiries = db.Table("enquiries")
negotiations = db.Table("negotiations")
offers = db.Table("negotiation_offers")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _expiry(days=3):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


# --- Enquiries --------------------------------------------------------------
def create_enquiry(*, product_id, buyer_id, farmer_id, required_qty=None,
                   delivery_district=None, expected_date=None, message=None,
                   is_advance=False):
    return enquiries.insert(
        product_id=product_id, buyer_id=buyer_id, farmer_id=farmer_id,
        required_qty=(str(required_qty) if required_qty is not None else None),
        delivery_district=delivery_district, expected_date=expected_date,
        message=message, is_advance=1 if is_advance else 0, status="open",
    )


def get_enquiry(enquiry_id):
    return enquiries.get(id=enquiry_id)


def enquiries_for_farmer(farmer_id):
    return db.query(
        "SELECT e.*, p.name AS product_name, p.unit AS unit, u.full_name AS buyer_name, "
        "bp.buyer_type AS buyer_type "
        "FROM enquiries e JOIN products p ON p.id=e.product_id "
        "JOIN buyer_profiles bp ON bp.id=e.buyer_id JOIN users u ON u.id=bp.user_id "
        "WHERE e.farmer_id=? ORDER BY e.created_at DESC", [farmer_id]
    )


def enquiries_for_buyer(buyer_id):
    return db.query(
        "SELECT e.*, p.name AS product_name, p.unit AS unit, f.display_name AS farmer_name "
        "FROM enquiries e JOIN products p ON p.id=e.product_id "
        "JOIN farmer_profiles f ON f.id=e.farmer_id "
        "WHERE e.buyer_id=? ORDER BY e.created_at DESC", [buyer_id]
    )


def set_enquiry_status(enquiry_id, status):
    enquiries.update({"id": enquiry_id}, status=status, updated_at=_now())


# --- Negotiations -----------------------------------------------------------
def get_or_create_negotiation(*, product_id, buyer_id, farmer_id, enquiry_id=None):
    existing = negotiations.get(
        product_id=product_id, buyer_id=buyer_id, farmer_id=farmer_id, is_open=1
    )
    if existing:
        return existing["id"]
    return negotiations.insert(
        product_id=product_id, buyer_id=buyer_id, farmer_id=farmer_id,
        enquiry_id=enquiry_id, is_open=1,
    )


def get_negotiation(negotiation_id):
    return negotiations.get(id=negotiation_id)


def close_negotiation(negotiation_id):
    negotiations.update({"id": negotiation_id}, is_open=0, updated_at=_now())


def negotiations_for_farmer(farmer_id):
    return db.query(
        "SELECT n.*, p.name AS product_name, u.full_name AS buyer_name, "
        "(SELECT COUNT(*) FROM negotiation_offers o WHERE o.negotiation_id=n.id) AS offer_count, "
        "(SELECT status FROM negotiation_offers o WHERE o.negotiation_id=n.id ORDER BY o.created_at DESC, o.rowid DESC LIMIT 1) AS last_status "
        "FROM negotiations n JOIN products p ON p.id=n.product_id "
        "JOIN buyer_profiles bp ON bp.id=n.buyer_id JOIN users u ON u.id=bp.user_id "
        "WHERE n.farmer_id=? ORDER BY n.updated_at DESC", [farmer_id]
    )


def negotiations_for_buyer(buyer_id):
    return db.query(
        "SELECT n.*, p.name AS product_name, f.display_name AS farmer_name, "
        "(SELECT COUNT(*) FROM negotiation_offers o WHERE o.negotiation_id=n.id) AS offer_count, "
        "(SELECT status FROM negotiation_offers o WHERE o.negotiation_id=n.id ORDER BY o.created_at DESC, o.rowid DESC LIMIT 1) AS last_status "
        "FROM negotiations n JOIN products p ON p.id=n.product_id "
        "JOIN farmer_profiles f ON f.id=n.farmer_id "
        "WHERE n.buyer_id=? ORDER BY n.updated_at DESC", [buyer_id]
    )


# --- Offers -----------------------------------------------------------------
def create_offer(*, negotiation_id, product_id, made_by, offered_qty,
                 offered_price, unit, message=None):
    # supersede the previous pending offer
    db.execute(
        "UPDATE negotiation_offers SET status='countered', updated_at=? "
        "WHERE negotiation_id=? AND status='pending'", [_now(), negotiation_id]
    )
    oid = offers.insert(
        negotiation_id=negotiation_id, product_id=product_id, made_by=made_by,
        offered_qty=str(offered_qty), offered_price=str(offered_price), unit=unit,
        message=message, status="pending", expires_at=_expiry(),
    )
    negotiations.update({"id": negotiation_id}, updated_at=_now())
    return oid


def offers_for_negotiation(negotiation_id):
    return offers.filter({"negotiation_id": negotiation_id}, order_by="created_at ASC, rowid ASC")


def get_offer(offer_id):
    return offers.get(id=offer_id)


def latest_offer(negotiation_id):
    rows = offers.filter({"negotiation_id": negotiation_id},
                         order_by="created_at DESC, rowid DESC", limit=1)
    return rows[0] if rows else None


def set_offer_status(offer_id, status):
    offers.update({"id": offer_id}, status=status, updated_at=_now())
