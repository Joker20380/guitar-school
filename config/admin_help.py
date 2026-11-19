from django.contrib import admin
from django.template.response import TemplateResponse
from django.views.decorators.http import require_safe


@require_safe
def admin_guide(request):
    return TemplateResponse(request, "admin/phoenix_guide.html", {
        **admin.site.each_context(request),
        "title": "Phoenix Song — инструкция администратора",
    })
