"""View helpers: template rendering with shared context, auth guards, messages."""
from __future__ import annotations

import functools

import settings
from core import security
from core.http import Response, forbidden, redirect
from core.i18n import LANGUAGE_NAMES
from core.templating import render_to_string


def render(request, template_name: str, context: dict | None = None,
           *, status: int = 200) -> Response:
    ctx = build_context(request, context or {})
    html = render_to_string(template_name, ctx)
    return Response(html, status=status)


def build_context(request, context: dict) -> dict:
    """Inject shared values available to every template."""
    lang = settings.DEFAULT_LANGUAGE
    user = getattr(request, "user", None)
    if request.session is not None:
        lang = request.session.get("lang", settings.DEFAULT_LANGUAGE)
        # ensure a CSRF token exists
        token = request.session.get("csrf_token")
        if not token:
            token = security.new_csrf_token()
            request.session["csrf_token"] = token
    else:
        token = ""
    base = {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "STATIC_URL": settings.STATIC_URL,
        "MEDIA_URL": settings.MEDIA_URL,
        "csrf_token": token,
        "user": user,
        "is_authenticated": user is not None,
        "lang": lang,
        "languages": LANGUAGE_NAMES,
        "messages": pop_messages(request),
        "current_year": 2026,
    }
    base.update(context)
    return base


# --- Flash messages ---------------------------------------------------------
def add_message(request, level: str, text: str) -> None:
    if request.session is None:
        return
    msgs = request.session.get("_messages", [])
    msgs.append({"level": level, "text": text})
    request.session["_messages"] = msgs


def pop_messages(request):
    if request.session is None:
        return []
    msgs = request.session.get("_messages", [])
    if msgs:
        request.session.pop("_messages")
    return msgs


# --- CSRF check (for POST handlers) -----------------------------------------
def csrf_ok(request) -> bool:
    import hmac as _hmac

    if request.method != "POST":
        return True
    submitted = request.POST("csrf_token") or request.environ.get("HTTP_X_CSRF_TOKEN")
    session_token = request.session.get("csrf_token") if request.session else None
    if not submitted or not session_token:
        return False
    # token must match the session token AND be a valid, unexpired signed token
    return _hmac.compare_digest(str(submitted), str(session_token)) and (
        security.csrf_token_valid(submitted)
    )


# --- Auth decorators --------------------------------------------------------
def login_required(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user is None:
            add_message(request, "error", "Please log in to continue.")
            return redirect(f"/login?next={request.path}")
        return view(request, *args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user is None:
                add_message(request, "error", "Please log in to continue.")
                return redirect(f"/login?next={request.path}")
            if request.user["role"] not in roles:
                return forbidden("You do not have permission to access this page.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
