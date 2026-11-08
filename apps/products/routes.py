from core.routing import router

from . import views

router.route(["GET", "POST"], "/farmer/products/new", views.product_create, name="product_create")
router.route(["GET"], "/farmer/products", views.product_list, name="product_list")
router.route(["GET", "POST"], "/farmer/products/<id>/edit", views.product_edit, name="product_edit")
router.route(["POST"], "/farmer/products/<id>/delete", views.product_delete, name="product_delete")
router.route(["POST"], "/farmer/products/<id>/status", views.product_status, name="product_status")
router.route(["GET", "POST"], "/farmer/inventory", views.inventory, name="inventory")
router.route(["POST"], "/farmer/products/<id>/stock", views.update_stock, name="update_stock")
router.route(["POST"], "/farmer/products/<id>/price", views.update_price, name="update_price")
router.route(["POST"], "/farmer/images/<image_id>/delete", views.delete_image_view, name="delete_image")
