"""Registration / login / profile forms with server-side validation."""
from __future__ import annotations

from core import forms

BUYER_TYPES = [
    "individual", "wholesaler", "retailer", "trader",
    "restaurant", "hotel", "food_processor", "distributor", "other_business",
]

BUYER_TYPE_LABELS = {
    "individual": "Individual Customer",
    "wholesaler": "Wholesaler",
    "retailer": "Retailer",
    "trader": "Agricultural Trader",
    "restaurant": "Restaurant",
    "hotel": "Hotel",
    "food_processor": "Food Processing Company",
    "distributor": "Distributor",
    "other_business": "Other Business",
}

LANGUAGES = ["en", "hi", "mr"]


class FarmerRegistrationForm(forms.Form):
    full_name = forms.CharField(min_length=2, max_length=120, label="Full name")
    mobile = forms.MobileField(label="Mobile number")
    email = forms.EmailField(required=False, label="Email (optional)")
    password = forms.CharField(min_length=6, max_length=128, label="Password")
    confirm_password = forms.CharField(min_length=6, max_length=128, label="Confirm password")
    village = forms.CharField(required=False, max_length=120, label="Village")
    taluka = forms.CharField(required=False, max_length=120, label="Taluka")
    district = forms.CharField(max_length=120, label="District")
    state = forms.CharField(required=False, default="Maharashtra", max_length=120)
    pincode = forms.PinField(required=False, label="PIN code")
    farm_location = forms.CharField(required=False, max_length=255, label="Farm location")
    total_land_acres = forms.DecimalField(required=False, min_value=0, label="Agricultural land (acres)")
    main_crops = forms.CharField(required=False, max_length=255, label="Main crops")
    preferred_language = forms.CharField(required=False, default="en", choices=LANGUAGES)

    def clean(self):
        if self.cleaned.get("password") != self.cleaned.get("confirm_password"):
            self.add_error("confirm_password", "Passwords do not match.")


class BuyerRegistrationForm(forms.Form):
    full_name = forms.CharField(min_length=2, max_length=120, label="Full name")
    business_name = forms.CharField(required=False, max_length=160, label="Business name (optional)")
    mobile = forms.MobileField(label="Mobile number")
    email = forms.EmailField(required=False, label="Email")
    password = forms.CharField(min_length=6, max_length=128, label="Password")
    confirm_password = forms.CharField(min_length=6, max_length=128, label="Confirm password")
    buyer_type = forms.CharField(choices=BUYER_TYPES, label="Buyer category")
    city = forms.CharField(required=False, max_length=120, label="City")
    district = forms.CharField(max_length=120, label="District")
    state = forms.CharField(required=False, default="Maharashtra", max_length=120)
    pincode = forms.PinField(required=False, label="PIN code")
    business_address = forms.CharField(required=False, max_length=255, label="Business address")
    gst_number = forms.CharField(required=False, max_length=20, label="GST number (optional)")

    def clean(self):
        if self.cleaned.get("password") != self.cleaned.get("confirm_password"):
            self.add_error("confirm_password", "Passwords do not match.")


class LoginForm(forms.Form):
    identifier = forms.CharField(label="Mobile or email")
    password = forms.CharField(label="Password")


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(label="Current password")
    new_password = forms.CharField(min_length=6, max_length=128, label="New password")
    confirm_password = forms.CharField(min_length=6, max_length=128, label="Confirm new password")

    def clean(self):
        if self.cleaned.get("new_password") != self.cleaned.get("confirm_password"):
            self.add_error("confirm_password", "Passwords do not match.")
