from core.routing import router

from . import views

router.get("/market-prices", views.market_prices, name="market_prices")
