"""Farmer product management: create, edit, delete, inventory, stock, price."""
from __future__ import annotations

from decimal import Decimal

from core.http import not_found, redirect
from core.uploads import UploadError, save_image
from core.views import add_message, render, role_required
from apps.accounts.models import get_farmer_by_user

from . import forms as pforms
from . import models


def _farmer(request):
    return get_farmer_by_user(request.user["id"])


def _owns(farmer, product):
    return product and farmer and product["farmer_id"] == farmer["id"]


@role_required("farmer")
def product_create(request):
    farmer = _farmer(request)
    form = pforms.ProductForm()
    if request.method == "POST":
        form = pforms.ProductForm(request.post_data)
        if form.is_valid():
            c = form.cleaned
            listing_type = c.get("listing_type") or "available"
            pid = models.create_product(
                farmer_id=farmer["id"],
                category_id=c.get("category_id") or None,
                name=c["name"], description=c.get("description"),
                grade=c.get("grade") or "ungraded",
                quality_notes=c.get("quality_notes"),
                farming_method=c.get("farming_method") or "conventional",
                unit=c["unit"], price=str(c["price"]),
                price_negotiable=1 if c.get("price_negotiable") else 0,
                min_order_qty=str(c["min_order_qty"]),
                max_order_qty=(str(c["max_order_qty"]) if c.get("max_order_qty") else None),
                sales_channel=c.get("sales_channel") or "both",
                wholesale_min_qty=(str(c["wholesale_min_qty"]) if c.get("wholesale_min_qty") else None),
                listing_type=listing_type,
                status="active",
                harvest_date=c.get("harvest_date"),
                expected_availability=c.get("expected_availability"),
                estimated_quantity=(str(c["estimated_quantity"]) if c.get("estimated_quantity") else None),
                expected_price=(str(c["expected_price"]) if c.get("expected_price") else None),
                freshness_info=c.get("freshness_info"),
                packaging_info=c.get("packaging_info"),
                pickup_available=1 if c.get("pickup_available") else 0,
                delivery_available=1 if c.get("delivery_available") else 0,
                village=c.get("village") or farmer.get("village"),
                taluka=c.get("taluka") or farmer.get("taluka"),
                district=c.get("district") or farmer["district"],
                state=c.get("state") or "Maharashtra",
                pincode=c.get("pincode"),
            )
            # initial stock
            qty = c.get("quantity") or Decimal("0")
            if qty and listing_type == "available":
                models.add_stock(pid, qty, note="Initial listing stock")
            # images
            _save_images(request, pid)
            add_message(request, "success", f"Product '{c['name']}' listed successfully.")
            return redirect("/farmer/products")
    return render(request, "products/product_form.html", {
        "form": {"data": form.data, "errors": form.errors},
        "categories": models.all_categories(),
        "units": [{"v": u, "l": models.UNIT_LABELS[u]} for u in models.UNITS],
        "grades": [{"v": g, "l": models.GRADE_LABELS[g]} for g in models.GRADES],
        "is_edit": False,
    })


@role_required("farmer")
def product_edit(request, id):
    farmer = _farmer(request)
    product = models.get_product(id)
    if not _owns(farmer, product):
        return not_found("Product not found")
    inventory = models.get_inventory(id)
    if request.method == "POST":
        form = pforms.ProductForm(request.post_data)
        if form.is_valid():
            c = form.cleaned
            models.update_product(
                id,
                category_id=c.get("category_id") or None,
                name=c["name"], description=c.get("description"),
                grade=c.get("grade") or "ungraded",
                quality_notes=c.get("quality_notes"),
                farming_method=c.get("farming_method") or "conventional",
                unit=c["unit"], price=str(c["price"]),
                price_negotiable=1 if c.get("price_negotiable") else 0,
                min_order_qty=str(c["min_order_qty"]),
                max_order_qty=(str(c["max_order_qty"]) if c.get("max_order_qty") else None),
                sales_channel=c.get("sales_channel") or "both",
                harvest_date=c.get("harvest_date"),
                packaging_info=c.get("packaging_info"),
                pickup_available=1 if c.get("pickup_available") else 0,
                delivery_available=1 if c.get("delivery_available") else 0,
                village=c.get("village"), taluka=c.get("taluka"),
                district=c.get("district") or farmer["district"],
                pincode=c.get("pincode"),
            )
            _save_images(request, id)
            add_message(request, "success", "Product updated.")
            return redirect("/farmer/products")
        data = form.data
        errors = form.errors
    else:
        data = dict(product)
        data["quantity"] = inventory["available_qty"] if inventory else "0"
        errors = {}
    return render(request, "products/product_form.html", {
        "form": {"data": data, "errors": errors},
        "product": product,
        "images": models.get_images(id),
        "categories": models.all_categories(),
        "units": [{"v": u, "l": models.UNIT_LABELS[u]} for u in models.UNITS],
        "grades": [{"v": g, "l": models.GRADE_LABELS[g]} for g in models.GRADES],
        "is_edit": True,
    })


@role_required("farmer")
def product_list(request):
    farmer = _farmer(request)
    rows = models.products_by_farmer(farmer["id"])
    for r in rows:
        inv = models.get_inventory(r["id"])
        r["available_qty"] = inv["available_qty"] if inv else "0"
        r["reserved_qty"] = inv["reserved_qty"] if inv else "0"
        img = models.primary_image(r["id"])
        r["image_path"] = img["path"] if img else None
        r["unit_label"] = models.UNIT_LABELS.get(r["unit"], r["unit"])
    return render(request, "products/product_list.html", {"products": rows})


@role_required("farmer")
def product_delete(request, id):
    farmer = _farmer(request)
    product = models.get_product(id)
    if not _owns(farmer, product):
        return not_found()
    models.delete_product(id)
    add_message(request, "success", "Listing deleted.")
    return redirect("/farmer/products")


@role_required("farmer")
def product_status(request, id):
    farmer = _farmer(request)
    product = models.get_product(id)
    if not _owns(farmer, product):
        return not_found()
    new_status = request.POST("status")
    if new_status in ("active", "paused", "sold_out"):
        models.update_product(id, status=new_status)
        add_message(request, "success", f"Listing marked {new_status.replace('_', ' ')}.")
    return redirect("/farmer/products")


@role_required("farmer")
def inventory(request):
    farmer = _farmer(request)
    rows = models.products_by_farmer(farmer["id"])
    for r in rows:
        inv = models.get_inventory(r["id"])
        r["available_qty"] = inv["available_qty"] if inv else "0"
        r["reserved_qty"] = inv["reserved_qty"] if inv else "0"
        r["sold_qty"] = inv["sold_qty"] if inv else "0"
        r["unit_label"] = models.UNIT_LABELS.get(r["unit"], r["unit"])
    return render(request, "products/inventory.html", {"products": rows})


@role_required("farmer")
def update_stock(request, id):
    farmer = _farmer(request)
    product = models.get_product(id)
    if not _owns(farmer, product):
        return not_found()
    try:
        new_qty = Decimal(str(request.POST("available_qty", "0")))
        if new_qty < 0:
            raise ValueError
        models.adjust_stock(id, new_qty, note="Farmer stock update")
        add_message(request, "success", "Stock updated.")
    except (ValueError, models.InventoryError) as e:
        add_message(request, "error", f"Could not update stock: {e}")
    return redirect("/farmer/inventory")


@role_required("farmer")
def update_price(request, id):
    farmer = _farmer(request)
    product = models.get_product(id)
    if not _owns(farmer, product):
        return not_found()
    try:
        price = Decimal(str(request.POST("price", "0")))
        if price < 0:
            raise ValueError
        models.update_product(id, price=str(price))
        add_message(request, "success", "Price updated.")
    except ValueError:
        add_message(request, "error", "Invalid price.")
    return redirect("/farmer/inventory")


@role_required("farmer")
def delete_image_view(request, image_id):
    models.delete_image(image_id)
    add_message(request, "success", "Image removed.")
    return redirect(request.POST("next") or "/farmer/products")


def _save_images(request, product_id):
    files = request.files_list("images")
    existing = len(models.get_images(product_id))
    saved = 0
    for f in files:
        if not f or not f.filename:
            continue
        if existing + saved >= 6:
            add_message(request, "info", "Maximum 6 images per product. Extra images skipped.")
            break
        try:
            path = save_image(f, "products")
            models.add_image(product_id, path, is_primary=(existing + saved == 0))
            saved += 1
        except UploadError as e:
            add_message(request, "error", f"Image skipped: {e}")
