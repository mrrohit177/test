"""Signed-cookie session store backed by the `sessions` DB table.

The cookie holds only a signed session id; all data lives server-side.
"""
from __future__ import annotations

import json
import time

import settings
from core import db, security

_sessions = db.Table("sessions", pk="id")


class Session:
    def __init__(self, sid: str, data: dict, is_new: bool):
        self.sid = sid
        self._data = data
        self.is_new = is_new
        self.modified = is_new

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value
        self.modified = True

    def __contains__(self, key):
        return key in self._data

    def pop(self, key, default=None):
        self.modified = True
        return self._data.pop(key, default)

    def clear(self):
        self._data = {}
        self.modified = True

    @property
    def data(self):
        return self._data


def load_session(request) -> Session:
    signed = request.cookies.get(settings.SESSION_COOKIE_NAME, "")
    sid = security.unsign(signed) if signed else None
    if sid:
        row = _sessions.get(id=sid)
        if row and row["expires_at"] > time.time():
            return Session(sid, json.loads(row["data"] or "{}"), is_new=False)
    # new session
    new_sid = db.new_uuid()
    return Session(new_sid, {}, is_new=True)


def save_session(session: Session, response) -> None:
    if not session.modified:
        return
    expires = time.time() + settings.SESSION_MAX_AGE
    payload = json.dumps(session.data)
    existing = _sessions.get(id=session.sid)
    if existing:
        _sessions.update({"id": session.sid}, data=payload, expires_at=expires)
    else:
        _sessions.insert(id=session.sid, data=payload, expires_at=expires,
                         created_at=time.time())
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        security.sign(session.sid),
        max_age=settings.SESSION_MAX_AGE,
        http_only=True,
        same_site="Lax",
    )


def destroy_session(session: Session, response) -> None:
    _sessions.delete(id=session.sid)
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
