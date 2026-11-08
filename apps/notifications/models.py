"""In-app notifications."""
from __future__ import annotations

from core import db

notifications = db.Table("notifications")


def notify(user_id, type_, title, body=None, link=None):
    return notifications.insert(
        user_id=user_id, type=type_, title=title, body=body, link=link, is_read=0
    )


def for_user(user_id, *, limit=50):
    return notifications.filter({"user_id": user_id}, order_by="created_at DESC", limit=limit)


def unread_count(user_id):
    return notifications.count({"user_id": user_id, "is_read": 0})


def mark_read(notification_id, user_id):
    notifications.update({"id": notification_id, "user_id": user_id}, is_read=1)


def mark_all_read(user_id):
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", [user_id])
