from core.routing import router

from . import views

router.get("/", views.home, name="home")
router.get("/products", views.browse, name="browse")
router.get("/products/<id>", views.product_detail, name="product_detail")
router.get("/categories", views.categories_page, name="categories")
router.get("/farmers", views.farmers_page, name="farmers")
router.get("/farmers/<farmer_id>", views.farmer_profile, name="farmer_profile")
router.get("/about", views.about, name="about")
router.route(["GET", "POST"], "/contact", views.contact, name="contact")
router.get("/how-it-works", views.how_it_works, name="how_it_works")
