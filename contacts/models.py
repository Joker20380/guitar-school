from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class ContactMessage(models.Model):
    STATUS_NEW = "new"
    STATUS_REPLIED = "replied"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_NEW, "Новое"),
        (STATUS_REPLIED, "Ответили"),
        (STATUS_ARCHIVED, "Архив"),
    ]

    CONTACT_EMAIL = "email"
    CONTACT_PHONE = "phone"
    CONTACT_TELEGRAM = "telegram"

    CONTACT_CHOICES = [
        (CONTACT_EMAIL, "Email"),
        (CONTACT_PHONE, "Телефон"),
        (CONTACT_TELEGRAM, "Telegram"),
    ]

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
