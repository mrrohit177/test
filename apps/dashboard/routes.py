from core.routing import router

from . import admin_views, views

# role dashboards
router.get("/dashboard", views.dashboard_home, name="dashboard")
router.get("/farmer/sales", views.sales_history, name="sales_history")
router.get("/buyer/history", views.purchase_history, name="purchase_history")
router.route(["GET", "POST"], "/buyer/wishlist", views.wishlist, name="wishlist")

# admin
router.get("/admin", admin_views.admin_home, name="admin_home")
router.get("/admin/farmers", admin_views.admin_farmers, name="admin_farmers")
router.post("/admin/farmers/<farmer_id>/verify", admin_views.admin_verify, name="admin_verify")
router.get("/admin/buyers", admin_views.admin_buyers, name="admin_buyers")
router.get("/admin/products", admin_views.admin_products, name="admin_products")
router.post("/admin/products/<id>/action", admin_views.admin_product_action, name="admin_product_action")
router.get("/admin/orders", admin_views.admin_orders, name="admin_orders")
router.route(["GET", "POST"], "/admin/complaints", admin_views.admin_complaints, name="admin_complaints")
router.get("/admin/reports", admin_views.admin_reports, name="admin_reports")
