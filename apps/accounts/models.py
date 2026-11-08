"""Account data access: users, farmer/buyer profiles, auth."""
from __future__ import annotations

from datetime import datetime, timezone

from core import db, security

users = db.Table("users")
farmer_profiles = db.Table("farmer_profiles")
buyer_profiles = db.Table("buyer_profiles")
addresses = db.Table("addresses")
audit_logs = db.Table("audit_logs")


# --- Users ------------------------------------------------------------------
def create_user(*, role, full_name, mobile, email, password,
                preferred_language="en", is_staff=False) -> str:
    return users.insert(
        role=role,
        full_name=full_name,
        mobile=mobile or None,
        email=(email or None),
        password_hash=security.hash_password(password),
        preferred_language=preferred_language,
        is_staff=1 if is_staff else 0,
        is_active=1,
    )


def get_user_by_id(user_id: str) -> dict | None:
    return users.get(id=user_id)


def get_user_by_mobile(mobile: str) -> dict | None:
    return users.get(mobile=mobile)


def get_user_by_email(email: str) -> dict | None:
    return users.get(email=email.lower()) if email else None


def authenticate(identifier: str, password: str) -> dict | None:
    """Identifier may be a mobile number or an email."""
    user = None
    digits = "".join(ch for ch in identifier if ch.isdigit())
    if len(digits) == 10:
        user = get_user_by_mobile(digits)
    if user is None and "@" in identifier:
        user = get_user_by_email(identifier)
    if user is None:
        user = get_user_by_mobile(identifier) or get_user_by_email(identifier)
    if user and user["is_active"] and security.verify_password(password, user["password_hash"]):
        users.update({"id": user["id"]}, last_login_at=_now())
        return user
    return None


def set_password(user_id: str, new_password: str) -> None:
    users.update({"id": user_id}, password_hash=security.hash_password(new_password))


def update_user(user_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    users.update({"id": user_id}, **fields)


# --- Farmer profiles --------------------------------------------------------
def create_farmer_profile(user_id, **fields) -> str:
    fields.setdefault("district", "")
    return farmer_profiles.insert(user_id=user_id, **fields)


def get_farmer_by_user(user_id: str) -> dict | None:
    return farmer_profiles.get(user_id=user_id)


def get_farmer(farmer_id: str) -> dict | None:
    return farmer_profiles.get(id=farmer_id)


def update_farmer(farmer_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    farmer_profiles.update({"id": farmer_id}, **fields)


# --- Buyer profiles ---------------------------------------------------------
def create_buyer_profile(user_id, **fields) -> str:
    return buyer_profiles.insert(user_id=user_id, **fields)


def get_buyer_by_user(user_id: str) -> dict | None:
    return buyer_profiles.get(user_id=user_id)


def get_buyer(buyer_id: str) -> dict | None:
    return buyer_profiles.get(id=buyer_id)


def update_buyer(buyer_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    buyer_profiles.update({"id": buyer_id}, **fields)


# --- Audit log --------------------------------------------------------------
def log_action(actor_id, action, *, entity=None, entity_id=None, detail=None, ip=None):
    audit_logs.insert(
        actor_id=actor_id, action=action, entity=entity,
        entity_id=entity_id, detail=detail, ip_address=ip,
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
