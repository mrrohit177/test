"""Product listing form."""
from __future__ import annotations

from core import forms
from . import models


class ProductForm(forms.Form):
    name = forms.CharField(min_length=2, max_length=160, label="Product name")
    category_id = forms.CharField(required=False, label="Category")
    description = forms.CharField(required=False, max_length=2000, label="Description")
    grade = forms.CharField(required=False, choices=models.GRADES, default="ungraded")
    quality_notes = forms.CharField(required=False, max_length=500)
    farming_method = forms.CharField(required=False, choices=models.METHODS, default="conventional")
    unit = forms.CharField(choices=models.UNITS, label="Unit")
    price = forms.DecimalField(min_value=0, label="Price")
    price_negotiable = forms.BoolField(label="Negotiable")
    quantity = forms.DecimalField(required=False, min_value=0, default=0, label="Quantity")
    min_order_qty = forms.DecimalField(min_value="0.0001", label="Minimum order quantity")
    max_order_qty = forms.DecimalField(required=False, min_value=0)
    sales_channel = forms.CharField(required=False, choices=models.CHANNELS, default="both")
    wholesale_min_qty = forms.DecimalField(required=False, min_value=0)
    listing_type = forms.CharField(required=False, choices=["available", "upcoming_harvest"], default="available")
    harvest_date = forms.DateField(required=False)
    expected_availability = forms.DateField(required=False)
    estimated_quantity = forms.DecimalField(required=False, min_value=0)
    expected_price = forms.DecimalField(required=False, min_value=0)
    freshness_info = forms.CharField(required=False, max_length=255)
    packaging_info = forms.CharField(required=False, max_length=255)
    pickup_available = forms.BoolField()
    delivery_available = forms.BoolField()
    village = forms.CharField(required=False, max_length=120)
    taluka = forms.CharField(required=False, max_length=120)
    district = forms.CharField(required=False, max_length=120)
    state = forms.CharField(required=False, default="Maharashtra", max_length=120)
    pincode = forms.PinField(required=False)

    def clean(self):
        # max >= min
        mn = self.cleaned.get("min_order_qty")
        mx = self.cleaned.get("max_order_qty")
        if mn and mx and mx < mn:
            self.add_error("max_order_qty", "Maximum must be at least the minimum order quantity.")
