from core.routing import router

from . import views

router.get("/notifications", views.notification_list, name="notifications")
router.post("/notifications/<id>/read", views.mark_read, name="notification_read")
router.post("/notifications/read-all", views.mark_all, name="notifications_read_all")
