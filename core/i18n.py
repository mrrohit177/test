"""Lightweight UI string translation for English / Hindi / Marathi.

Falls back to English, then to the key itself. Add keys as the UI grows.
"""
from __future__ import annotations

import settings

STRINGS: dict[str, dict[str, str]] = {
    "nav.home": {"en": "Home", "hi": "होम", "mr": "मुख्यपृष्ठ"},
    "nav.browse": {"en": "Browse Products", "hi": "उत्पाद देखें", "mr": "उत्पादने पहा"},
    "nav.categories": {"en": "Categories", "hi": "श्रेणियाँ", "mr": "श्रेणी"},
    "nav.farmers": {"en": "Find Farmers", "hi": "किसान खोजें", "mr": "शेतकरी शोधा"},
    "nav.market_prices": {"en": "Market Prices", "hi": "बाज़ार भाव", "mr": "बाजारभाव"},
    "nav.about": {"en": "About Us", "hi": "हमारे बारे में", "mr": "आमच्याबद्दल"},
    "nav.contact": {"en": "Contact", "hi": "संपर्क", "mr": "संपर्क"},
    "nav.login": {"en": "Login", "hi": "लॉगिन", "mr": "लॉगिन"},
    "nav.register": {"en": "Register", "hi": "रजिस्टर", "mr": "नोंदणी"},
    "nav.dashboard": {"en": "Dashboard", "hi": "डैशबोर्ड", "mr": "डॅशबोर्ड"},
    "nav.logout": {"en": "Logout", "hi": "लॉगआउट", "mr": "बाहेर पडा"},
    "hero.headline": {
        "en": "Buy Directly from Farmers. Sell Without Middlemen.",
        "hi": "सीधे किसानों से खरीदें। बिचौलियों के बिना बेचें।",
        "mr": "थेट शेतकऱ्यांकडून खरेदी करा. दलालांशिवाय विक्री करा.",
    },
    "hero.subtitle": {
        "en": "Discover fresh agricultural products, compare prices and connect directly with farmers across India.",
        "hi": "ताज़े कृषि उत्पाद खोजें, कीमतों की तुलना करें और पूरे भारत के किसानों से सीधे जुड़ें।",
        "mr": "ताजी कृषी उत्पादने शोधा, किंमतींची तुलना करा आणि संपूर्ण भारतातील शेतकऱ्यांशी थेट संपर्क साधा.",
    },
    "cta.start_selling": {"en": "Start Selling", "hi": "बेचना शुरू करें", "mr": "विक्री सुरू करा"},
    "cta.start_buying": {"en": "Start Buying", "hi": "खरीदना शुरू करें", "mr": "खरेदी सुरू करा"},
    "cta.explore": {"en": "Explore Products", "hi": "उत्पाद देखें", "mr": "उत्पादने पहा"},
    "search.placeholder": {
        "en": "What agricultural product are you looking for?",
        "hi": "आप कौन सा कृषि उत्पाद खोज रहे हैं?",
        "mr": "तुम्ही कोणते कृषी उत्पादन शोधत आहात?",
    },
}

LANGUAGE_NAMES = {"en": "English", "hi": "हिंदी", "mr": "मराठी"}


def translate(key: str, lang: str | None = None) -> str:
    lang = lang if lang in settings.LANGUAGES else settings.DEFAULT_LANGUAGE
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(settings.DEFAULT_LANGUAGE) or key
