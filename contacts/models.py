from django.db import models

from config.i18n import bilingual as bt
from phonenumber_field.modelfields import PhoneNumberField


class ContactMessage(models.Model):
    STATUS_NEW = "new"
    STATUS_REPLIED = "replied"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_NEW, bt("New", "Новое")),
        (STATUS_REPLIED, bt("Replied", "Ответили")),
        (STATUS_ARCHIVED, bt("Archived", "Архив")),
    ]

    CONTACT_EMAIL = "email"
    CONTACT_PHONE = "phone"
    CONTACT_TELEGRAM = "telegram"
    CONTACT_WHATSAPP = "whatsapp"
    CONTACT_OTHER = "other"

    CONTACT_CHOICES = [
        (CONTACT_EMAIL, bt("Email", "Электронная почта")),
        (CONTACT_PHONE, bt("Phone", "Телефон")),
        (CONTACT_TELEGRAM, bt("Telegram", "Телеграм")),
        (CONTACT_WHATSAPP, "WhatsApp"),
        (CONTACT_OTHER, bt("Another way", "Другой способ")),
    ]

    DIRECTION_CHOICES = [
        ("russian", bt("Russian through music", "Русский язык через музыку")),
        ("guitar", bt("Guitar and musical creativity", "Гитара и музыкальное творчество")),
        ("undecided", bt("I haven't decided yet", "Пока не определился / определилась")),
    ]
    direction = models.CharField("Направление", max_length=20, choices=DIRECTION_CHOICES, blank=True)
    other_contact = models.CharField("Другой контакт", max_length=200, blank=True)
    submission_key = models.UUIDField("Ключ отправки", null=True, blank=True, unique=True, editable=False)
    NOTIFICATION_CHOICES = [("disabled", "Отключено"), ("accepted", "Принято сервисом, доставка не подтверждена"), ("failed", "Ошибка")]
    email_notification_status = models.CharField("Email уведомление", max_length=12, default="disabled", choices=NOTIFICATION_CHOICES)
    telegram_notification_status = models.CharField("Telegram уведомление", max_length=12, default="disabled", choices=NOTIFICATION_CHOICES)

    name = models.CharField("Имя", max_length=120)
    email = models.EmailField("Email", blank=True)
    phone = PhoneNumberField("Телефон", region="BE", blank=True)
    telegram = models.CharField("Telegram", max_length=80, blank=True)

    preferred_contact = models.CharField(
        "Удобный способ связи",
        max_length=32,
        choices=CONTACT_CHOICES,
        default=CONTACT_EMAIL,
    )

    subject = models.CharField("Тема", max_length=180, blank=True)
    message = models.TextField("Сообщение")

    status = models.CharField("Статус", max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW)

    ip_address = models.GenericIPAddressField("IP-адрес", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=300, blank=True)

    created_at = models.DateTimeField("Дата сообщения", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Сообщение с сайта"
        verbose_name_plural = "Сообщения с сайта"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.subject or 'Без темы'}"
