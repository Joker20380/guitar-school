from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation


class PublicLocaleMiddleware(LocaleMiddleware):
    """Keep the public site in English until the visitor explicitly chooses Russian."""

    def process_request(self, request):
        requested = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, "")
        requested = requested.split("-", 1)[0].lower()
        available = {code for code, _label in settings.LANGUAGES}
        language = requested if requested in available else settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = language
