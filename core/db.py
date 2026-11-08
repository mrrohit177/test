"""SQLite data layer + a tiny ORM-style query helper.

Design goals:
 - Thin wrapper over sqlite3 with row dict access.
 - Foreign keys + WAL enabled.
 - A `Table` helper giving insert/get/filter/update/delete so feature code
   reads close to an ORM. Schema is PostgreSQL-compatible (see schema.sql).
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from typing import Any, Iterable, Mapping

import settings

_local = threading.local()


def new_uuid() -> str:
    return str(uuid.uuid4())


def get_connection() -> sqlite3.Connection:
    """One connection per thread (wsgiref may use threads)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        settings.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(settings.DATABASE_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        _local.conn = conn
    return conn


def close_connection() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def query(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    cur = get_connection().execute(sql, tuple(params))
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    cur = get_connection().execute(sql, tuple(params))
    row = cur.fetchone()
    return dict(row) if row else None


def execute(sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    conn = get_connection()
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur


def executescript(script: str) -> None:
    conn = get_connection()
    conn.executescript(script)
    conn.commit()


class transaction:
    """Context manager for atomic multi-statement operations.

    Usage:
        with transaction():
            ...db writes...
    Rolls back on exception, commits on success.
    """

    def __enter__(self):
        self.conn = get_connection()
        self.conn.execute("BEGIN")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False


class Table:
    """Minimal query helper bound to a single table."""

    def __init__(self, name: str, *, pk: str = "id"):
        self.name = name
        self.pk = pk

    # -- create --
    def insert(self, **values: Any) -> str:
        if self.pk == "id" and "id" not in values:
            values["id"] = new_uuid()
        cols = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        execute(
            f"INSERT INTO {self.name} ({cols}) VALUES ({placeholders})",
            list(values.values()),
        )
        return values.get(self.pk)

    # -- read --
    def get(self, **where: Any) -> dict | None:
        clause, params = _where(where)
        return query_one(f"SELECT * FROM {self.name} WHERE {clause} LIMIT 1", params)

    def filter(
        self,
        where: Mapping[str, Any] | None = None,
        *,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        sql = f"SELECT * FROM {self.name}"
        params: list[Any] = []
        if where:
            clause, params = _where(where)
            sql += f" WHERE {clause}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset is not None:
            sql += f" OFFSET {int(offset)}"
        return query(sql, params)

    def all(self, *, order_by: str | None = None) -> list[dict]:
        return self.filter(order_by=order_by)

    def count(self, where: Mapping[str, Any] | None = None) -> int:
        sql = f"SELECT COUNT(*) AS c FROM {self.name}"
        params: list[Any] = []
        if where:
            clause, params = _where(where)
            sql += f" WHERE {clause}"
        row = query_one(sql, params)
        return int(row["c"]) if row else 0

    # -- update --
    def update(self, where: Mapping[str, Any], **values: Any) -> int:
        set_clause = ", ".join(f"{k} = ?" for k in values)
        where_clause, where_params = _where(where)
        cur = execute(
            f"UPDATE {self.name} SET {set_clause} WHERE {where_clause}",
            list(values.values()) + where_params,
        )
        return cur.rowcount

    # -- delete --
    def delete(self, **where: Any) -> int:
        clause, params = _where(where)
        cur = execute(f"DELETE FROM {self.name} WHERE {clause}", params)
        return cur.rowcount


def _where(where: Mapping[str, Any]) -> tuple[str, list[Any]]:
    parts, params = [], []
    for key, val in where.items():
        if val is None:
            parts.append(f"{key} IS NULL")
        else:
            parts.append(f"{key} = ?")
            params.append(val)
    return " AND ".join(parts) if parts else "1=1", params
