from django.conf import settings
from django.contrib import admin
from django.template.response import TemplateResponse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_safe


@require_safe
def admin_guide(request):
    document = (settings.BASE_DIR / "docs" / "admin-guide-ru.html").read_text(encoding="utf-8")
    # Only the trusted, repository-owned guide body is embedded. The standalone
    # document's light-only styles are replaced by the admin's native theme.
    guide_body = document.split("<main>", 1)[1].split("</main>", 1)[0]
    return TemplateResponse(request, "admin/guide.html", {
        **admin.site.each_context(request),
        "title": "Инструкция администратора",
        "guide_body": mark_safe(guide_body),
    })
