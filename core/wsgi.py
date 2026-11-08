"""WSGI application: ties routing, sessions, auth, static/media serving.

Middleware order per request:
  1. Build Request
  2. Load session
  3. Resolve current user from session
  4. Serve static/media OR dispatch to router
  5. CSRF enforcement on POST
  6. Save session, emit Response
"""
from __future__ import annotations

import mimetypes
import traceback

import settings
from core import sessions
from core.http import Request, Response, forbidden, not_found
from core.routing import router
from core.views import add_message, csrf_ok


def application(environ, start_response):
    request = Request(environ)
    response: Response

    try:
        # static & media are served before session handling (no cookies needed)
        if request.path.startswith(settings.STATIC_URL):
            response = _serve_file(settings.STATIC_DIR, request.path[len(settings.STATIC_URL):])
            return _finish(response, start_response)
        if request.path.startswith(settings.MEDIA_URL):
            response = _serve_file(settings.MEDIA_DIR, request.path[len(settings.MEDIA_URL):])
            return _finish(response, start_response)

        # session + user
        request.session = sessions.load_session(request)
        request.user = _resolve_user(request)

        handler, params = router.match(request)
        if handler is None:
            response = _render_404(request)
        elif handler == "__405__":
            response = Response("Method not allowed", status=405)
        else:
            request.url_params = params or {}
            # CSRF enforcement for state-changing requests
            if request.method == "POST" and not csrf_ok(request):
                add_message(request, "error", "Security check failed. Please try again.")
                response = forbidden("CSRF verification failed.")
            else:
                result = handler(request, **(params or {}))
                response = result if isinstance(result, Response) else Response(str(result))

        sessions.save_session(request.session, response)
        return _finish(response, start_response)

    except Exception as exc:  # noqa: BLE001
        if settings.DEBUG:
            body = (
                "<h1>500 Internal Server Error</h1><pre>"
                + traceback.format_exc()
                + "</pre>"
            )
        else:
            body = "<h1>Something went wrong</h1><p>Please try again later.</p>"
        response = Response(body, status=500)
        return _finish(response, start_response)


def _resolve_user(request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    from apps.accounts.models import get_user_by_id

    return get_user_by_id(uid)


def _serve_file(base_dir, rel_path) -> Response:
    # prevent path traversal
    safe = (base_dir / rel_path).resolve()
    try:
        safe.relative_to(base_dir.resolve())
    except ValueError:
        return forbidden("Invalid path")
    if not safe.is_file():
        return not_found("File not found")
    ctype, _ = mimetypes.guess_type(str(safe))
    data = safe.read_bytes()
    return Response(data, content_type=ctype or "application/octet-stream")


def _render_404(request) -> Response:
    try:
        from core.views import render

        return render(request, "404.html", {}, status=404)
    except Exception:
        return not_found()


def _finish(response: Response, start_response):
    start_response(response.status_line(), response.header_list())
    return [response.body]
