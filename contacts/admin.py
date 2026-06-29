from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "preferred_contact",
        "email",
        "phone",
        "telegram",
        "subject",
        "status",
        "created_at",
    )
    list_filter = ("status", "preferred_contact", "created_at")
    search_fields = ("name", "email", "phone", "telegram", "subject", "message")
    readonly_fields = ("created_at", "updated_at", "ip_address", "user_agent")
    fields = (
        "status",
        "name",
        "email",
        "phone",
        "telegram",
        "preferred_contact",
        "subject",
        "message",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    )
