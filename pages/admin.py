from django.contrib import admin
from .models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("name", "is_published", "created_at")
    list_filter = ("is_published",)
    search_fields = ("name", "text")
    readonly_fields = ("created_at",)
    fields = ("name", "text", "photo", "user", "is_published", "created_at")
    actions = ("publish",)

    @admin.action(description="Опубликовать проверенные отзывы")
    def publish(self, request, queryset):
        queryset.update(is_published=True)
