"""
FarmConnect global settings.

Secrets are read from environment variables where possible, falling back to
development defaults. NEVER use the development SECRET_KEY in production.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Security ---------------------------------------------------------------
# Override in production:  export FARMCONNECT_SECRET_KEY="..."
SECRET_KEY = os.environ.get(
    "FARMCONNECT_SECRET_KEY",
    "dev-insecure-key-change-me-in-production-0123456789abcdef",
)
DEBUG = os.environ.get("FARMCONNECT_DEBUG", "1") == "1"

# --- Database ---------------------------------------------------------------
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = Path(os.environ.get("FARMCONNECT_DB", DATABASE_DIR / "farmconnect.sqlite3"))

# --- Media / static ---------------------------------------------------------
MEDIA_DIR = BASE_DIR / "media"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

MEDIA_URL = "/media/"
STATIC_URL = "/static/"

# Upload rules
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB per file
MAX_PRODUCT_IMAGES = 6

# --- Sessions ---------------------------------------------------------------
SESSION_COOKIE_NAME = "fc_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 days
CSRF_COOKIE_NAME = "fc_csrf"

# --- Password hashing -------------------------------------------------------
PBKDF2_ITERATIONS = 260_000

# --- Server -----------------------------------------------------------------
HOST = os.environ.get("FARMCONNECT_HOST", "127.0.0.1")
PORT = int(os.environ.get("FARMCONNECT_PORT", "8000"))

# --- Branding ---------------------------------------------------------------
SITE_NAME = "FarmConnect"
SITE_TAGLINE = "Connecting Farmers. Empowering Buyers. Growing Together."
DEFAULT_STATE = "Maharashtra"

# --- i18n -------------------------------------------------------------------
DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "hi", "mr")

# --- Market price data source (optional, honest empty state if unset) -------
# Set to the data.gov.in AGMARKNET resource key to enable live market prices.
DATA_GOV_IN_API_KEY = os.environ.get("DATA_GOV_IN_API_KEY", "")
