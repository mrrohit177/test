"""Read-optimised queries that join products with farmer, image, inventory.

Returns enriched dict rows ready for product cards / listings.
"""
from __future__ import annotations

from core import db

PRODUCT_LABELS_UNIT = {
    "kg": "kg", "quintal": "quintal", "metric_ton": "ton", "gram": "g",
    "litre": "litre", "dozen": "dozen", "piece": "piece", "bag": "bag", "box": "box",
}
GRADE_LABELS = {"grade_a": "Grade A", "grade_b": "Grade B", "grade_c": "Grade C", "ungraded": "Ungraded"}

_BASE = """
SELECT
    p.*,
    f.display_name          AS farmer_name,
    f.verification_level    AS farmer_verification,
    f.rating_avg            AS farmer_rating,
    f.district              AS farmer_district,
    f.village               AS farmer_village,
    c.name_en               AS category_name,
    c.slug                  AS category_slug,
    inv.available_qty       AS available_qty,
    inv.reserved_qty        AS reserved_qty,
    (SELECT pi.path FROM product_images pi
       WHERE pi.product_id = p.id
       ORDER BY pi.is_primary DESC, pi.sort_order LIMIT 1) AS image_path
FROM products p
JOIN farmer_profiles f  ON f.id = p.farmer_id
LEFT JOIN product_categories c ON c.id = p.category_id
LEFT JOIN product_inventory inv ON inv.product_id = p.id
"""

SORTS = {
    "price_asc": "p.price ASC",
    "price_desc": "p.price DESC",
    "recent": "p.created_at DESC",
    "quantity": "CAST(inv.available_qty AS REAL) DESC",
    "rating": "f.rating_avg DESC",
}


def _enrich(rows):
    for r in rows:
        r["unit_label"] = PRODUCT_LABELS_UNIT.get(r["unit"], r["unit"])
        r["grade_label"] = GRADE_LABELS.get(r["grade"], r["grade"])
        r["is_verified"] = r["farmer_verification"] in (
            "identity_verified", "farm_verified"
        )
        r["is_organic"] = r["farming_method"] == "organic"
    return rows


def featured(limit=8):
    rows = db.query(
        _BASE + " WHERE p.status='active' AND p.listing_type='available'"
        " ORDER BY p.view_count DESC, p.created_at DESC LIMIT ?", [limit]
    )
    return _enrich(rows)


def recent(limit=8):
    rows = db.query(
        _BASE + " WHERE p.status='active' AND p.listing_type='available'"
        " ORDER BY p.created_at DESC LIMIT ?", [limit]
    )
    return _enrich(rows)


def wholesale(limit=8):
    rows = db.query(
        _BASE + " WHERE p.status='active' AND p.listing_type='available'"
        " AND p.sales_channel IN ('wholesale','both')"
        " ORDER BY p.created_at DESC LIMIT ?", [limit]
    )
    return _enrich(rows)


def upcoming_harvests(limit=8):
    rows = db.query(
        _BASE + " WHERE p.status='active' AND p.listing_type='upcoming_harvest'"
        " ORDER BY p.expected_availability ASC LIMIT ?", [limit]
    )
    return _enrich(rows)


def near_district(district, limit=8):
    rows = db.query(
        _BASE + " WHERE p.status='active' AND p.listing_type='available'"
        " AND p.district = ? ORDER BY p.created_at DESC LIMIT ?", [district, limit]
    )
    return _enrich(rows)


def get_detail(product_id):
    rows = db.query(_BASE + " WHERE p.id = ?", [product_id])
    return _enrich(rows)[0] if rows else None


def by_farmer(farmer_id, *, exclude=None, limit=12):
    sql = _BASE + " WHERE p.farmer_id = ? AND p.status='active'"
    params = [farmer_id]
    if exclude:
        sql += " AND p.id != ?"
        params.append(exclude)
    sql += " ORDER BY p.created_at DESC LIMIT ?"
    params.append(limit)
    return _enrich(db.query(sql, params))


def search(*, q=None, category_slug=None, district=None, grade=None,
           method=None, channel=None, min_price=None, max_price=None,
           verified_only=False, delivery_only=False, listing_type="available",
           sort="recent", limit=24, offset=0):
    """Full marketplace search with filters + sorting. Returns (rows, total)."""
    where = ["p.status='active'", "p.listing_type = ?"]
    params = [listing_type]

    if q:
        where.append("(p.name LIKE ? OR f.display_name LIKE ? OR p.village LIKE ?"
                     " OR p.taluka LIKE ? OR p.district LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like, like, like]
    if category_slug:
        where.append("c.slug = ?")
        params.append(category_slug)
    if district:
        where.append("p.district = ?")
        params.append(district)
    if grade:
        where.append("p.grade = ?")
        params.append(grade)
    if method:
        where.append("p.farming_method = ?")
        params.append(method)
    if channel in ("retail", "wholesale"):
        where.append("p.sales_channel IN (?, 'both')")
        params.append(channel)
    if min_price:
        where.append("CAST(p.price AS REAL) >= ?")
        params.append(float(min_price))
    if max_price:
        where.append("CAST(p.price AS REAL) <= ?")
        params.append(float(max_price))
    if verified_only:
        where.append("f.verification_level IN ('identity_verified','farm_verified')")
    if delivery_only:
        where.append("p.delivery_available = 1")

    where_sql = " AND ".join(where)
    order = SORTS.get(sort, SORTS["recent"])

    # count
    count_sql = (
        "SELECT COUNT(*) AS c FROM products p "
        "JOIN farmer_profiles f ON f.id = p.farmer_id "
        "LEFT JOIN product_categories c ON c.id = p.category_id "
        "LEFT JOIN product_inventory inv ON inv.product_id = p.id "
        f"WHERE {where_sql}"
    )
    total = db.query_one(count_sql, params)["c"]

    rows = db.query(
        _BASE + f" WHERE {where_sql} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    return _enrich(rows), total


def distinct_districts():
    rows = db.query(
        "SELECT DISTINCT district FROM products WHERE status='active' ORDER BY district"
    )
    return [r["district"] for r in rows if r["district"]]
