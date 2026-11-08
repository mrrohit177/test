# FarmConnect — Security Notes

## Authentication & passwords
- Passwords are hashed with **PBKDF2-HMAC-SHA256**, 260,000 iterations, a unique
  per-user 16-byte salt. Encoded form: `pbkdf2_sha256$<iterations>$<salt>$<hash>`.
  (`core/security.py`)
- Verification is constant-time (`hmac.compare_digest`).
- Passwords are never logged or stored in plaintext.

## Sessions
- Server-side sessions stored in the `sessions` table; the cookie holds only an
  HMAC-signed session id (`core/sessions.py`).
- Cookies are `HttpOnly` and `SameSite=Lax`. Set `secure=True` behind HTTPS.
- On login the session id is rotated (old session data cleared) to mitigate
  session fixation.

## CSRF
- Every state-changing `POST` requires a valid `csrf_token` that (a) matches the
  token stored in the session and (b) is a valid, unexpired HMAC-signed token
  (`core/security.py::csrf_token_valid`, enforced in `core/wsgi.py`).

## Authorization (RBAC)
- `login_required` and `role_required(...)` decorators guard every private view
  (`core/views.py`). A user can never open another user's dashboard, order,
  negotiation, or product — ownership is checked against the profile id.

## File uploads
- Uploads are validated by **extension allow-list**, **size limit** (5 MB), and a
  **magic-byte** image sniff — client-supplied content type is not trusted
  (`core/uploads.py`). Files are stored under `media/` with a random name; the
  original filename/path is discarded to prevent traversal.
- Static/media serving rejects path traversal (`core/wsgi.py::_serve_file`).

## Data privacy
- Identity / land / business documents go into `verification_documents` with a
  **private** storage path and are never rendered on public pages. Only an admin
  verification workflow reads them.
- Public farmer profiles never expose mobile/email without consent.

## SQL
- All queries are parameterised (`?` placeholders) — no string interpolation of
  user input into SQL (`core/db.py`).

## Secrets
- `FARMCONNECT_SECRET_KEY` is read from the environment. The bundled default is
  clearly marked insecure and **must** be overridden in production.

## Inventory integrity
- Stock changes run inside a DB transaction and can never go negative; overselling
  is impossible because reservations check availability under a row lock
  (`apps/products/models.py::_adjust`).

## Production hardening checklist
- [ ] Set a strong `FARMCONNECT_SECRET_KEY`.
- [ ] Set `FARMCONNECT_DEBUG=0` (hides tracebacks).
- [ ] Serve over HTTPS and set session cookie `secure=True`.
- [ ] Put a real WSGI server (gunicorn/uWSGI) + reverse proxy in front.
- [ ] Move `media/` behind an authenticated handler for private documents.
- [ ] Migrate SQLite → PostgreSQL (schema is already compatible).
