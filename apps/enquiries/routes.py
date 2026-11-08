from core.routing import router

from . import views

router.post("/enquiries/create", views.create_enquiry, name="create_enquiry")
router.get("/negotiations/<id>", views.negotiation_detail, name="negotiation_detail")
router.post("/negotiations/<id>/respond", views.respond_offer, name="respond_offer")
router.get("/farmer/enquiries", views.farmer_enquiries, name="farmer_enquiries")
router.get("/farmer/negotiations", views.farmer_negotiations, name="farmer_negotiations")
router.get("/buyer/enquiries", views.buyer_enquiries, name="buyer_enquiries")
router.get("/buyer/negotiations", views.buyer_negotiations, name="buyer_negotiations")
