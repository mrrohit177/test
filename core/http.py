"""Request and Response objects for the WSGI layer."""
from __future__ import annotations

import json
import urllib.parse
from http.cookies import SimpleCookie
from typing import Any, Mapping


class Request:
    def __init__(self, environ: Mapping[str, Any]):
        self.environ = environ
        self.method = environ.get("REQUEST_METHOD", "GET").upper()
        self.path = environ.get("PATH_INFO", "/") or "/"
        self.query_string = environ.get("QUERY_STRING", "")
        self._query = urllib.parse.parse_qs(self.query_string)
        self._body_cache: bytes | None = None
        self._post: dict[str, Any] | None = None
        self._files: dict[str, Any] | None = None
        self.cookies = self._parse_cookies()
        # populated by middleware:
        self.session = None
        self.user = None
        self.url_params: dict[str, str] = {}

    def _parse_cookies(self) -> dict[str, str]:
        raw = self.environ.get("HTTP_COOKIE", "")
        jar = SimpleCookie()
        if raw:
            jar.load(raw)
        return {k: m.value for k, m in jar.items()}

    @property
    def body(self) -> bytes:
        if self._body_cache is None:
            try:
                length = int(self.environ.get("CONTENT_LENGTH", 0) or 0)
            except (ValueError, TypeError):
                length = 0
            stream = self.environ.get("wsgi.input")
            self._body_cache = stream.read(length) if (stream and length) else b""
        return self._body_cache

    @property
    def content_type(self) -> str:
        return self.environ.get("CONTENT_TYPE", "")

    def GET(self, key: str, default: str | None = None) -> str | None:
        vals = self._query.get(key)
        return vals[0] if vals else default

    def GET_list(self, key: str) -> list[str]:
        return self._query.get(key, [])

    @property
    def query(self) -> dict[str, list[str]]:
        return self._query

    def _ensure_post_parsed(self):
        if self._post is not None:
            return
        from core.uploads import parse_multipart  # local import to avoid cycle

        self._post, self._files = {}, {}
        ctype = self.content_type
        if self.method in ("POST", "PUT", "PATCH"):
            if ctype.startswith("application/x-www-form-urlencoded"):
                parsed = urllib.parse.parse_qs(self.body.decode("utf-8", "replace"))
                self._post = {k: v[0] for k, v in parsed.items()}
                self._post_lists = {k: v for k, v in parsed.items()}
            elif ctype.startswith("multipart/form-data"):
                self._post, self._files = parse_multipart(ctype, self.body)
            elif ctype.startswith("application/json"):
                try:
                    self._post = json.loads(self.body.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    self._post = {}

    def POST(self, key: str, default: Any = None) -> Any:
        self._ensure_post_parsed()
        return self._post.get(key, default)

    @property
    def post_data(self) -> dict[str, Any]:
        self._ensure_post_parsed()
        return self._post

    def FILES(self, key: str):
        self._ensure_post_parsed()
        return self._files.get(key)

    def files_list(self, key: str) -> list:
        self._ensure_post_parsed()
        f = self._files.get(key)
        if f is None:
            return []
        return f if isinstance(f, list) else [f]

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None


class Response:
    def __init__(
        self,
        body: str | bytes = "",
        *,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        headers: list[tuple[str, str]] | None = None,
    ):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status
        self.headers = headers or []
        self._has_ct = any(h[0].lower() == "content-type" for h in self.headers)
        if not self._has_ct:
            self.headers.append(("Content-Type", content_type))
        self._cookies = SimpleCookie()

    STATUS_TEXT = {
        200: "OK", 201: "Created", 204: "No Content",
        302: "Found", 303: "See Other", 304: "Not Modified",
        400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
        404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large",
        500: "Internal Server Error",
    }

    def set_cookie(self, name, value, *, max_age=None, http_only=True,
                   same_site="Lax", path="/", secure=False):
        self._cookies[name] = value
        c = self._cookies[name]
        c["path"] = path
        if max_age is not None:
            c["max-age"] = int(max_age)
        if http_only:
            c["httponly"] = True
        if secure:
            c["secure"] = True
        if same_site:
            c["samesite"] = same_site

    def delete_cookie(self, name, path="/"):
        self._cookies[name] = ""
        self._cookies[name]["path"] = path
        self._cookies[name]["max-age"] = 0

    def status_line(self) -> str:
        return f"{self.status} {self.STATUS_TEXT.get(self.status, 'OK')}"

    def header_list(self) -> list[tuple[str, str]]:
        out = list(self.headers)
        for morsel in self._cookies.values():
            out.append(("Set-Cookie", morsel.OutputString()))
        return out


# --- Response helpers -------------------------------------------------------
def redirect(location: str, *, status: int = 303) -> Response:
    return Response(status=status, headers=[("Location", location)])


def json_response(data: Any, *, status: int = 200) -> Response:
    return Response(
        json.dumps(data), status=status, content_type="application/json; charset=utf-8"
    )


def not_found(message: str = "Page not found") -> Response:
    return Response(message, status=404)


def forbidden(message: str = "Forbidden") -> Response:
    return Response(message, status=403)
