from core.routing import router

from . import views

router.post("/orders/create-from-offer", views.create_from_offer, name="create_from_offer")
router.post("/orders/create-direct", views.create_direct, name="create_direct")
router.get("/orders/<id>", views.order_detail, name="order_detail")
router.post("/orders/<id>/status", views.update_status, name="order_status")
router.get("/farmer/orders", views.farmer_orders, name="farmer_orders")
router.get("/buyer/orders", views.buyer_orders, name="buyer_orders")
