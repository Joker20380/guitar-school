from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "published_at", "updated_at")
    list_filter = ("is_published", "published_at")
    list_editable = ("is_published",)
    search_fields = ("title", "title_ru", "excerpt", "excerpt_ru", "content", "content_ru")
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        ("English", {"fields": ("title", "slug", "excerpt", "content")} ),
        ("Русский", {"fields": ("title_ru", "excerpt_ru", "content_ru")} ),
        ("Медиа", {"fields": ("photo_file", "photo_url", "video_url")} ),
        ("Публикация", {"fields": ("is_published", "published_at")} ),
    )
