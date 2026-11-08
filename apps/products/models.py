"""Products, categories, images, and inventory data access + inventory service."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from core import db

products = db.Table("products")
product_images = db.Table("product_images")
product_inventory = db.Table("product_inventory")
inventory_movements = db.Table("inventory_movements")
categories = db.Table("product_categories")

UNITS = ["kg", "quintal", "metric_ton", "gram", "litre", "dozen", "piece", "bag", "box"]
UNIT_LABELS = {
    "kg": "Kilogram", "quintal": "Quintal", "metric_ton": "Metric Ton",
    "gram": "Gram", "litre": "Litre", "dozen": "Dozen", "piece": "Piece",
    "bag": "Bag", "box": "Box",
}
GRADES = ["grade_a", "grade_b", "grade_c", "ungraded"]
GRADE_LABELS = {"grade_a": "Grade A", "grade_b": "Grade B", "grade_c": "Grade C", "ungraded": "Ungraded"}
METHODS = ["organic", "conventional", "natural", "mixed"]
CHANNELS = ["retail", "wholesale", "both"]


# --- Categories -------------------------------------------------------------
def all_categories():
    return categories.filter({"is_active": 1}, order_by="sort_order, name_en")


def get_category(category_id):
    return categories.get(id=category_id)


def get_category_by_slug(slug):
    return categories.get(slug=slug)


# --- Products ---------------------------------------------------------------
def create_product(**fields) -> str:
    fields["created_at"] = _now()
    fields["updated_at"] = _now()
    fields["price_updated_at"] = _now()
    pid = products.insert(**fields)
    # initialise inventory
    product_inventory.insert(
        product_id=pid,
        available_qty=str(fields.get("initial_qty", 0)) if "initial_qty" in fields else "0",
        reserved_qty="0", sold_qty="0",
    )
    return pid


def get_product(product_id):
    return products.get(id=product_id)


def update_product(product_id, **fields):
    fields["updated_at"] = _now()
    if "price" in fields:
        fields["price_updated_at"] = _now()
    products.update({"id": product_id}, **fields)


def delete_product(product_id):
    # soft delete to preserve order history integrity
    products.update({"id": product_id}, status="deleted", updated_at=_now())


def get_images(product_id):
    return product_images.filter({"product_id": product_id}, order_by="is_primary DESC, sort_order")


def primary_image(product_id):
    imgs = get_images(product_id)
    return imgs[0] if imgs else None


def add_image(product_id, path, *, is_primary=False, sort_order=0):
    return product_images.insert(
        product_id=product_id, path=path,
        is_primary=1 if is_primary else 0, sort_order=sort_order,
    )


def delete_image(image_id):
    product_images.delete(id=image_id)


def get_inventory(product_id):
    return product_inventory.get(product_id=product_id)


def increment_views(product_id):
    db.execute("UPDATE products SET view_count = view_count + 1 WHERE id = ?", [product_id])


def increment_enquiries(product_id):
    db.execute("UPDATE products SET enquiry_count = enquiry_count + 1 WHERE id = ?", [product_id])


def products_by_farmer(farmer_id, *, include_deleted=False):
    where = {"farmer_id": farmer_id}
    rows = products.filter(where, order_by="created_at DESC")
    if not include_deleted:
        rows = [r for r in rows if r["status"] != "deleted"]
    return rows


# --- Inventory service (atomic, never negative, no overselling) -------------
class InventoryError(Exception):
    pass


def _adjust(product_id, movement_type, qty, *, reference=None, note=None):
    """Atomic inventory adjustment. qty is a positive Decimal."""
    qty = Decimal(str(qty))
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT available_qty, reserved_qty, sold_qty FROM product_inventory "
            "WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise InventoryError("No inventory record for product")
        available = Decimal(str(row["available_qty"]))
        reserved = Decimal(str(row["reserved_qty"]))
        sold = Decimal(str(row["sold_qty"]))

        if movement_type in ("add", "adjustment"):
            available += qty
        elif movement_type == "reservation":
            if available < qty:
                raise InventoryError(
                    f"Insufficient stock: {available} available, {qty} requested."
                )
            available -= qty
            reserved += qty
        elif movement_type == "release":
            release_amt = min(reserved, qty)
            reserved -= release_amt
            available += release_amt
        elif movement_type == "sale":
            # commit previously reserved stock to sold
            commit_amt = min(reserved, qty)
            reserved -= commit_amt
            sold += commit_amt
        elif movement_type == "spoilage":
            available = max(Decimal("0"), available - qty)
        else:
            raise InventoryError(f"Unknown movement type {movement_type}")

        conn.execute(
            "UPDATE product_inventory SET available_qty=?, reserved_qty=?, sold_qty=?, "
            "updated_at=? WHERE product_id=?",
            (str(available), str(reserved), str(sold), _now(), product_id),
        )
        conn.execute(
            "INSERT INTO inventory_movements (id, product_id, movement_type, quantity, "
            "balance_after, reference_id, note, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (db.new_uuid(), product_id, movement_type, str(qty), str(available),
             reference, note, _now()),
        )
    return available


def add_stock(product_id, qty, *, note="Stock added"):
    return _adjust(product_id, "add", qty, note=note)


def reserve_stock(product_id, qty, *, reference=None):
    return _adjust(product_id, "reservation", qty, reference=reference, note="Reserved for order")


def release_stock(product_id, qty, *, reference=None):
    return _adjust(product_id, "release", qty, reference=reference, note="Released (order cancelled)")


def commit_sale(product_id, qty, *, reference=None):
    return _adjust(product_id, "sale", qty, reference=reference, note="Order completed")


def adjust_stock(product_id, new_available, *, note="Manual adjustment"):
    """Set available stock to an absolute value (farmer updates quantity)."""
    inv = get_inventory(product_id)
    if inv is None:
        raise InventoryError("No inventory record")
    current = Decimal(str(inv["available_qty"]))
    target = Decimal(str(new_available))
    delta = target - current
    if delta == 0:
        return current
    if delta > 0:
        return _adjust(product_id, "add", delta, note=note)
    return _adjust(product_id, "spoilage", -delta, note=note)


def movements_for(product_id, limit=50):
    return inventory_movements.filter(
        {"product_id": product_id}, order_by="created_at DESC", limit=limit
    )


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
