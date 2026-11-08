"""Market Price Tracker.

Shows APMC market prices if data has been loaded (via seed/import). If no data
source is configured and no data exists, shows an honest empty state. We never
fabricate live prices.
"""
from __future__ import annotations

import settings
from core import db
from core.views import render


def market_prices(request):
    commodity = request.GET("commodity", "")
    district = request.GET("district", "")

    sql = "SELECT * FROM market_prices WHERE 1=1"
    params = []
    if commodity:
        sql += " AND LOWER(commodity) LIKE LOWER(?)"
        params.append(f"%{commodity}%")
    if district:
        sql += " AND district = ?"
        params.append(district)
    sql += " ORDER BY arrival_date DESC, commodity LIMIT 200"
    rows = db.query(sql, params)

    commodities = [r["commodity"] for r in db.query(
        "SELECT DISTINCT commodity FROM market_prices ORDER BY commodity")]
    districts = [r["district"] for r in db.query(
        "SELECT DISTINCT district FROM market_prices ORDER BY district")]

    last_updated = db.query_one(
        "SELECT MAX(arrival_date) AS d, MAX(created_at) AS c FROM market_prices")

    data_source_configured = bool(settings.DATA_GOV_IN_API_KEY)

    return render(request, "market_prices/index.html", {
        "prices": rows,
        "commodities": commodities,
        "districts": districts,
        "commodity": commodity,
        "district": district,
        "has_data": len(rows) > 0 or bool(commodities),
        "last_updated": last_updated["d"] if last_updated else None,
        "data_source_configured": data_source_configured,
    })
