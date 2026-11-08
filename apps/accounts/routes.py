from core.routing import router

from . import views

router.route(["GET"], "/register", views.register_choice, name="register")
router.route(["GET", "POST"], "/register/farmer", views.register_farmer, name="register_farmer")
router.route(["GET", "POST"], "/register/buyer", views.register_buyer, name="register_buyer")
router.route(["GET", "POST"], "/login", views.login_view, name="login")
router.route(["GET", "POST"], "/logout", views.logout_view, name="logout")
router.route(["GET", "POST"], "/profile", views.profile, name="profile")
router.route(["GET", "POST"], "/settings", views.settings_view, name="settings")
router.route(["GET", "POST"], "/set-language", views.set_language, name="set_language")
