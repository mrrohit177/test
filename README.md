# 🌾 FarmConnect — Agricultural Marketplace

> **Connecting Farmers. Empowering Buyers. Growing Together.**

FarmConnect is an India-first digital marketplace that connects farmers directly
with buyers (individuals, wholesalers, retailers, traders, restaurants, hotels and
businesses), removing middlemen from the agricultural supply chain. The initial
target market is **Maharashtra, India**, with an architecture designed to scale
across the country.

---

## ⚙️ Technology & why this build is dependency-free

This application is written in **pure Python 3 (standard library only)** —
**no pip packages, no Node.js, no npm, no React, no build step.**

> **Why not Django?** The project was specified for Django, but it is developed in
> a sandbox where the Python package index (PyPI) is **network-blocked**, so
> `pip install django` is impossible here. Rather than ship untested code, this
> MVP reimplements the small slice of framework plumbing it needs (routing,
> sessions, CSRF, password hashing, a tiny ORM) on top of the standard library,
> so the app **actually runs, persists data, and passes its tests in this
> environment today**.
>
> All framework plumbing is isolated in the [`core/`](core/) package, and the
> data model mirrors Django model semantics, so migrating to real Django later is
> a contained change rather than a rewrite. See
> [`docs/DJANGO_MIGRATION.md`](docs/DJANGO_MIGRATION.md).

| Layer       | Technology                                             |
|-------------|--------------------------------------------------------|
| Language    | Python 3.11 (stdlib only)                              |
| Web server  | `wsgiref` (dev) — WSGI-compatible for gunicorn/uWSGI   |
| Database    | SQLite 3 (via `sqlite3`) — PostgreSQL-compatible schema|
| Templates   | Server-rendered HTML (custom template engine)          |
| Auth        | PBKDF2-HMAC-SHA256 password hashing, signed cookie sessions |
| Security    | CSRF tokens, role-based access control, secure uploads |
| Frontend    | HTML5 + custom CSS3 + vanilla JavaScript               |

---

## 🚀 Quick start

```bash
# From the project root — no install step required.
python3 manage.py migrate     # create the SQLite database + tables
python3 manage.py seed        # load demo data (clearly marked as DEMO)
python3 manage.py runserver   # start the dev server at http://127.0.0.1:8000
```

Then open **http://127.0.0.1:8000** in your browser.

### Demo accounts (created by `seed`)

| Role   | Login (mobile) | Password     |
|--------|----------------|--------------|
| Admin  | `9000000000`   | `admin1234`  |
| Farmer | `9811111111`   | `farmer1234` |
| Buyer  | `9822222222`   | `buyer1234`  |

Run the test suite:

```bash
python3 manage.py test
```

---

## 📁 Project structure

```
farmconnect/
├── manage.py                # CLI: migrate | seed | runserver | test
├── settings.py              # configuration (env-overridable secrets)
├── core/                    # framework plumbing (the "Django-lite" layer)
│   ├── db.py                # SQLite connection + tiny ORM / query helpers
│   ├── http.py              # Request / Response objects
│   ├── routing.py           # URL router
│   ├── templating.py        # server-side template engine
│   ├── sessions.py          # signed-cookie session store
│   ├── security.py          # password hashing, CSRF, signing
│   ├── forms.py             # server-side form validation
│   ├── uploads.py           # secure multipart file upload handling
│   └── wsgi.py              # WSGI application entry point
├── apps/                    # feature modules (like Django apps)
│   ├── accounts/            # users, auth, registration, profiles
│   ├── products/            # categories, products, images, inventory
│   ├── marketplace/         # public browse, search, filters, product detail
│   ├── enquiries/           # enquiries + negotiation/offers
│   ├── orders/              # order lifecycle + inventory reservation
│   ├── dashboard/           # farmer / buyer / admin dashboards
│   ├── notifications/       # in-app notifications
│   ├── logistics/           # transport coordination
│   └── market_prices/       # APMC market price tracker
├── templates/               # HTML templates
├── static/                  # css / js
├── media/                   # uploaded product + profile images (gitignored)
├── database/                # SQLite db file lives here (gitignored)
├── tests/                   # test suite
└── docs/                    # migration notes
```

---

## ✅ Feature checklist

- [x] Custom user model with roles (farmer / buyer / admin)
- [x] Farmer & buyer registration, login, logout, profile
- [x] Secure password hashing + CSRF + session management
- [x] Product listings, multiple photos, inventory (never negative)
- [x] Marketplace browse, search, filters, sorting
- [x] Product detail + enquiries + price negotiation
- [x] Order lifecycle with inventory reservation (no overselling)
- [x] Farmer / buyer / admin dashboards (all data-backed)
- [x] In-app notifications
- [x] Transport coordination module
- [x] Market price tracker (honest empty state — no fake live prices)
- [x] Demo data + automated tests

---

## 🔐 Security notes

- Passwords hashed with PBKDF2-HMAC-SHA256 (260k iterations, per-user salt).
- Session cookies are HMAC-signed, `HttpOnly`, `SameSite=Lax`.
- CSRF token required on all state-changing POST requests.
- Role-based access control guards every private dashboard and action.
- Uploaded files are extension/size validated and stored outside the web root
  logic (served through a controlled handler).
- Identity/verification documents are **never** exposed publicly.
- Secrets read from environment variables (`FARMCONNECT_SECRET_KEY`).

See [`docs/SECURITY.md`](docs/SECURITY.md).

---

## 🌐 Internationalization

UI strings are centralised for **English / Hindi / Marathi** with a language
switcher. English is the default. See `core/i18n.py`.

---

_Demo data is clearly labelled and must not be treated as real transactions._
