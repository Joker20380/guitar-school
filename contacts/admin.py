from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "direction",
        "preferred_contact",
        "email",
        "phone",
        "telegram",
        "subject",
        "status",
        "created_at",
    )
    list_filter = ("status", "direction", "preferred_contact", "created_at")
    search_fields = ("name", "email", "phone", "telegram", "other_contact", "subject", "message")
    readonly_fields = ("created_at", "updated_at", "ip_address", "user_agent", "submission_key", "email_notification_status", "telegram_notification_status")
    fields = (
        "status",
        "name",
        "direction",
        "email",
        "phone",
        "telegram",
        "other_contact",
        "preferred_contact",
        "subject",
        "message",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
        "submission_key",
        "email_notification_status",
        "telegram_notification_status",
    )
