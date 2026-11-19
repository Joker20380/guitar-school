from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class AdminLocaleMiddleware(MiddlewareMixin):
    """Use Russian for staff administration, keeping public language selection intact."""

    def process_request(self, request):
        if request.path_info == "/admin" or request.path_info.startswith("/admin/"):
            translation.activate("ru")
            request.LANGUAGE_CODE = "ru"
