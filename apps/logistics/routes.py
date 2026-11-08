from core.routing import router

from . import views

router.get("/transport", views.transport_list, name="transport")
router.route(["GET", "POST"], "/transport/new", views.transport_create, name="transport_create")
