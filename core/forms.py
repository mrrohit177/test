"""Minimal server-side form validation.

Never trusts client-side validation. Returns cleaned data + field errors.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")  # Indian 10-digit mobile
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PIN_RE = re.compile(r"^\d{6}$")
GST_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


class Field:
    def __init__(
        self,
        *,
        required: bool = True,
        label: str | None = None,
        validators: list[Callable] | None = None,
        choices: list | None = None,
        default: Any = None,
    ):
        self.required = required
        self.label = label
        self.validators = validators or []
        self.choices = choices
        self.default = default

    def clean(self, value):
        if value in (None, ""):
            if self.required:
                raise ValueError("This field is required.")
            return self.default
        value = self.to_python(value)
        if self.choices is not None and value not in self.choices:
            raise ValueError("Invalid choice.")
        for v in self.validators:
            v(value)
        return value

    def to_python(self, value):
        return value


class CharField(Field):
    def __init__(self, *, min_length=0, max_length=None, **kw):
        super().__init__(**kw)
        self.min_length = min_length
        self.max_length = max_length

    def to_python(self, value):
        value = str(value).strip()
        if self.min_length and len(value) < self.min_length:
            raise ValueError(f"Must be at least {self.min_length} characters.")
        if self.max_length and len(value) > self.max_length:
            raise ValueError(f"Must be at most {self.max_length} characters.")
        return value


class EmailField(CharField):
    def to_python(self, value):
        value = super().to_python(value)
        if value and not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address.")
        return value.lower()


class MobileField(CharField):
    def to_python(self, value):
        value = re.sub(r"\D", "", str(value))
        if not MOBILE_RE.match(value):
            raise ValueError("Enter a valid 10-digit Indian mobile number.")
        return value


class PinField(CharField):
    def to_python(self, value):
        value = str(value).strip()
        if value and not PIN_RE.match(value):
            raise ValueError("Enter a valid 6-digit PIN code.")
        return value


class DecimalField(Field):
    def __init__(self, *, min_value=None, max_value=None, **kw):
        super().__init__(**kw)
        self.min_value = min_value
        self.max_value = max_value

    def to_python(self, value):
        try:
            d = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            raise ValueError("Enter a valid number.")
        if self.min_value is not None and d < Decimal(str(self.min_value)):
            raise ValueError(f"Must be at least {self.min_value}.")
        if self.max_value is not None and d > Decimal(str(self.max_value)):
            raise ValueError(f"Must be at most {self.max_value}.")
        return d


class IntField(Field):
    def to_python(self, value):
        try:
            return int(str(value).strip())
        except ValueError:
            raise ValueError("Enter a whole number.")


class BoolField(Field):
    def __init__(self, **kw):
        kw.setdefault("required", False)
        kw.setdefault("default", False)
        super().__init__(**kw)

    def clean(self, value):
        return str(value).lower() in ("1", "true", "on", "yes")


class DateField(CharField):
    def to_python(self, value):
        value = str(value).strip()
        if value and not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            raise ValueError("Enter a date as YYYY-MM-DD.")
        return value or None


class Form:
    """Subclass and declare fields as class attributes."""

    fields: dict[str, Field] = {}

    def __init__(self, data: dict[str, Any] | None = None):
        self.data = data or {}
        self.cleaned: dict[str, Any] = {}
        self.errors: dict[str, str] = {}

    @classmethod
    def _declared_fields(cls) -> dict[str, Field]:
        out = {}
        for klass in reversed(cls.__mro__):
            for name, val in vars(klass).items():
                if isinstance(val, Field):
                    out[name] = val
        return out

    def is_valid(self) -> bool:
        self.errors = {}
        self.cleaned = {}
        for name, field in self._declared_fields().items():
            raw = self.data.get(name)
            try:
                self.cleaned[name] = field.clean(raw)
            except ValueError as e:
                self.errors[name] = str(e)
        self.clean()
        return not self.errors

    def clean(self):
        """Override for cross-field validation; add to self.errors."""
        pass

    def add_error(self, field: str, message: str):
        self.errors[field] = message
