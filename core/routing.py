"""A small URL router supporting <param> path segments.

Patterns look like:  /products/<id>/edit  or  /farmer/<farmer_id>
Matched params are placed on request.url_params.
"""
from __future__ import annotations

import re
from typing import Callable

from core.http import Request, Response

_PARAM_RE = re.compile(r"<([a-zA-Z_][a-zA-Z0-9_]*)>")


class Route:
    def __init__(self, methods, pattern: str, handler: Callable, name: str | None):
        self.methods = {m.upper() for m in methods}
        self.pattern = pattern
        self.handler = handler
        self.name = name
        self.regex = self._compile(pattern)

    @staticmethod
    def _compile(pattern: str) -> re.Pattern:
        regex = _PARAM_RE.sub(lambda m: f"(?P<{m.group(1)}>[^/]+)", pattern)
        return re.compile(f"^{regex}/?$")


class Router:
    def __init__(self):
        self.routes: list[Route] = []
        self._by_name: dict[str, str] = {}

    def add(self, methods, pattern, handler, name=None):
        route = Route(methods, pattern, handler, name)
        self.routes.append(route)
        if name:
            self._by_name[name] = pattern

    # convenience decorators / helpers
    def get(self, pattern, handler, name=None):
        self.add(["GET"], pattern, handler, name)

    def post(self, pattern, handler, name=None):
        self.add(["POST"], pattern, handler, name)

    def route(self, methods, pattern, handler, name=None):
        self.add(methods, pattern, handler, name)

    def include(self, other: "Router"):
        self.routes.extend(other.routes)
        self._by_name.update(other._by_name)

    def match(self, request: Request):
        """Return (handler, params) or (None, None). Raises 405 marker if path
        matches but method does not."""
        path_matched = False
        for route in self.routes:
            m = route.regex.match(request.path)
            if m:
                path_matched = True
                if request.method in route.methods:
                    return route.handler, m.groupdict()
        if path_matched:
            return "__405__", None
        return None, None

    def url(self, name: str, **params) -> str:
        pattern = self._by_name.get(name)
        if pattern is None:
            raise KeyError(f"No route named {name!r}")
        for key, val in params.items():
            pattern = pattern.replace(f"<{key}>", str(val))
        return pattern


# global router instance, populated by apps on import
router = Router()
