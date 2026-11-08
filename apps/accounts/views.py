"""Account views: register (farmer/buyer), login, logout, profile, settings."""
from __future__ import annotations

from core import security
from core.http import redirect
from core.uploads import UploadError, save_image
from core.views import add_message, login_required, render

from . import forms, models


# --- Registration landing ---------------------------------------------------
def register_choice(request):
    return render(request, "accounts/register_choice.html")


# --- Farmer registration -----------------------------------------------------
def register_farmer(request):
    if request.user:
        return redirect("/dashboard")
    form = forms.FarmerRegistrationForm()
    if request.method == "POST":
        form = forms.FarmerRegistrationForm(request.post_data)
        if form.is_valid():
            c = form.cleaned
            if models.get_user_by_mobile(c["mobile"]):
                form.add_error("mobile", "This mobile number is already registered.")
            elif c.get("email") and models.get_user_by_email(c["email"]):
                form.add_error("email", "This email is already registered.")
            else:
                uid = models.create_user(
                    role="farmer", full_name=c["full_name"], mobile=c["mobile"],
                    email=c.get("email"), password=c["password"],
                    preferred_language=c.get("preferred_language") or "en",
                )
                models.create_farmer_profile(
                    uid,
                    display_name=c["full_name"],
                    village=c.get("village"), taluka=c.get("taluka"),
                    district=c["district"], state=c.get("state") or "Maharashtra",
                    pincode=c.get("pincode"), farm_location=c.get("farm_location"),
                    total_land_acres=(str(c["total_land_acres"]) if c.get("total_land_acres") is not None else None),
                    main_crops=c.get("main_crops"),
                    verification_level="basic",
                )
                models.log_action(uid, "register_farmer", entity="user", entity_id=uid)
                _login_session(request, uid)
                add_message(request, "success",
                            "Welcome to FarmConnect! Your farmer account is ready.")
                return redirect("/dashboard")
    return render(request, "accounts/register_farmer.html", {"form": _form_ctx(form)})


# --- Buyer registration ------------------------------------------------------
def register_buyer(request):
    if request.user:
        return redirect("/dashboard")
    form = forms.BuyerRegistrationForm()
    if request.method == "POST":
        form = forms.BuyerRegistrationForm(request.post_data)
        if form.is_valid():
            c = form.cleaned
            if models.get_user_by_mobile(c["mobile"]):
                form.add_error("mobile", "This mobile number is already registered.")
            elif c.get("email") and models.get_user_by_email(c["email"]):
                form.add_error("email", "This email is already registered.")
            else:
                uid = models.create_user(
                    role="buyer", full_name=c["full_name"], mobile=c["mobile"],
                    email=c.get("email"), password=c["password"],
                )
                models.create_buyer_profile(
                    uid,
                    buyer_type=c["buyer_type"], business_name=c.get("business_name"),
                    city=c.get("city"), district=c["district"],
                    state=c.get("state") or "Maharashtra", pincode=c.get("pincode"),
                    business_address=c.get("business_address"),
                    gst_number=c.get("gst_number"),
                )
                models.log_action(uid, "register_buyer", entity="user", entity_id=uid)
                _login_session(request, uid)
                add_message(request, "success",
                            "Welcome to FarmConnect! Your buyer account is ready.")
                return redirect("/dashboard")
    return render(request, "accounts/register_buyer.html", {
        "form": _form_ctx(form),
        "buyer_types": [{"value": v, "label": forms.BUYER_TYPE_LABELS[v]} for v in forms.BUYER_TYPES],
    })


# --- Login / logout ----------------------------------------------------------
def login_view(request):
    if request.user:
        return redirect("/dashboard")
    form = forms.LoginForm()
    next_url = request.GET("next", "/dashboard")
    if request.method == "POST":
        form = forms.LoginForm(request.post_data)
        next_url = request.POST("next") or "/dashboard"
        if form.is_valid():
            user = models.authenticate(form.cleaned["identifier"], form.cleaned["password"])
            if user:
                _login_session(request, user["id"])
                models.log_action(user["id"], "login")
                add_message(request, "success", f"Welcome back, {user['full_name']}!")
                return redirect(next_url if next_url.startswith("/") else "/dashboard")
            add_message(request, "error", "Invalid credentials. Please try again.")
    return render(request, "accounts/login.html", {"form": _form_ctx(form), "next": next_url})


def logout_view(request):
    if request.user:
        models.log_action(request.user["id"], "logout")
    request.session.clear()
    add_message(request, "success", "You have been logged out.")
    return redirect("/")


# --- Profile / settings ------------------------------------------------------
@login_required
def profile(request):
    user = request.user
    profile_data = None
    if user["role"] == "farmer":
        profile_data = models.get_farmer_by_user(user["id"])
    elif user["role"] == "buyer":
        profile_data = models.get_buyer_by_user(user["id"])

    if request.method == "POST":
        full_name = (request.POST("full_name") or "").strip()
        if full_name:
            models.update_user(user["id"], full_name=full_name)
        # avatar upload (optional)
        avatar = request.FILES("avatar")
        if avatar and avatar.filename:
            try:
                path = save_image(avatar, "profiles")
                models.update_user(user["id"], avatar_path=path)
            except UploadError as e:
                add_message(request, "error", f"Avatar upload failed: {e}")
        # role-specific fields
        if user["role"] == "farmer" and profile_data:
            models.update_farmer(
                profile_data["id"],
                village=(request.POST("village") or profile_data["village"]),
                taluka=(request.POST("taluka") or profile_data["taluka"]),
                district=(request.POST("district") or profile_data["district"]),
                bio=(request.POST("bio") or profile_data.get("bio")),
                main_crops=(request.POST("main_crops") or profile_data.get("main_crops")),
            )
        elif user["role"] == "buyer" and profile_data:
            models.update_buyer(
                profile_data["id"],
                business_name=(request.POST("business_name") or profile_data.get("business_name")),
                city=(request.POST("city") or profile_data.get("city")),
                district=(request.POST("district") or profile_data.get("district")),
                business_address=(request.POST("business_address") or profile_data.get("business_address")),
            )
        add_message(request, "success", "Profile updated.")
        return redirect("/profile")

    return render(request, "accounts/profile.html", {"profile": profile_data})


@login_required
def settings_view(request):
    form = forms.PasswordChangeForm()
    if request.method == "POST":
        action = request.POST("action")
        if action == "change_password":
            form = forms.PasswordChangeForm(request.post_data)
            if form.is_valid():
                if not security.verify_password(form.cleaned["current_password"],
                                                request.user["password_hash"]):
                    form.add_error("current_password", "Current password is incorrect.")
                else:
                    models.set_password(request.user["id"], form.cleaned["new_password"])
                    add_message(request, "success", "Password changed successfully.")
                    return redirect("/settings")
        elif action == "change_language":
            lang = request.POST("lang", "en")
            if lang in ("en", "hi", "mr"):
                request.session["lang"] = lang
                models.update_user(request.user["id"], preferred_language=lang)
                add_message(request, "success", "Language updated.")
                return redirect("/settings")
    return render(request, "accounts/settings.html", {"form": _form_ctx(form)})


def set_language(request):
    """Public language switch (works for logged-out visitors too)."""
    lang = request.POST("lang") or request.GET("lang") or "en"
    if lang in ("en", "hi", "mr"):
        request.session["lang"] = lang
    return redirect(request.POST("next") or request.GET("next") or "/")


# --- helpers -----------------------------------------------------------------
def _login_session(request, user_id):
    # rotate session id defense: clear then set
    request.session.clear()
    request.session["user_id"] = user_id
    request.session["csrf_token"] = security.new_csrf_token()


def _form_ctx(form):
    """Expose form data + errors to templates."""
    return {"data": form.data, "errors": form.errors}
