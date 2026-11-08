# Migrating FarmConnect to Django

This project was specified for **Django**, but was built in a sandbox where the
Python package index (PyPI) is network-blocked, so `pip install django` was
impossible. To deliver a *running, tested* application, the small amount of
framework plumbing Django would provide was reimplemented on the Python standard
library, isolated in [`core/`](../core). Everything else (data model, business
logic, templates, URLs) is already written the way it would be under Django, so
the migration below is contained.

## What maps directly (little/no change)

| FarmConnect (stdlib)                 | Django equivalent                         |
|--------------------------------------|-------------------------------------------|
| `core/schema.sql` tables             | `models.py` in each app (field types map 1:1; schema is already PostgreSQL-compatible) |
| `apps/<x>/models.py` query helpers   | Django ORM querysets / managers           |
| `apps/<x>/views.py`                  | Django function views (signatures nearly identical) |
| `apps/<x>/routes.py`                 | `urls.py` (`path("...", view, name=...)`) |
| `core/forms.py` Form/Field classes   | `django.forms.Form` / `ModelForm`         |
| `templates/*.html`                   | Django templates — syntax was kept Django-like (`{% block %}`, `{% for %}`, `{% if %}`, `{{ x|filter }}`, `{% csrf %}` → `{% csrf_token %}`) |
| `core/security.py` password hashing  | Django's PBKDF2 hasher (same algorithm)   |
| `core/sessions.py`                   | `django.contrib.sessions`                 |
| `core/views.py` `role_required`      | decorators / `UserPassesTestMixin`        |
| `apps/.../admin_views.py`            | custom admin views + `django.contrib.admin`|

## Steps

1. On a machine **with internet**: `pip install django`.
2. `django-admin startproject config .` and `python manage.py startapp <name>`
   for each folder in `apps/`.
3. Add a **custom user model** (`AUTH_USER_MODEL`) mirroring the `users` table
   (role, mobile, preferred_language) **before** the first migration.
4. Translate each `core/schema.sql` table into `models.py`. The column types,
   constraints, and FKs are already chosen to map cleanly; UUID PKs →
   `UUIDField(primary_key=True, default=uuid.uuid4)`.
5. Replace the query-helper calls (`Table(...).get/filter/insert/update`) with
   ORM calls. The call sites are thin and localised.
6. Point `settings.DATABASES` at PostgreSQL (the schema is already PG-safe).
7. Rename `{% csrf %}` → `{% csrf_token %}`; otherwise templates work as-is under
   Django's engine (the custom engine was built to match Django semantics).
8. Port the tests in `tests/` to Django's `TestCase` + test client — the flows
   (register → list → enquire → negotiate → order → complete) translate directly.

## Why the behaviour is preserved
The business rules that matter — inventory reservation/commit, no overselling,
multi-seller order split, offer/counteroffer lifecycle, RBAC — live in
`apps/*/models.py` and `apps/*/views.py`, not in the plumbing. Moving the
plumbing to Django does not change those rules.
