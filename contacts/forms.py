import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.html import strip_tags
from phonenumber_field.formfields import PhoneNumberField

from .models import ContactMessage


URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁёІіЇїЄє'\-\s]{2,80}$")
TELEGRAM_RE = re.compile(r"^@?[A-Za-z0-9_][A-Za-z0-9_.\-]{2,78}$")


class ContactMessageForm(forms.ModelForm):
    phone = PhoneNumberField(
        required=False,
        region="BE",
        label="Телефон",
        error_messages={
            "invalid": "Введите корректный номер телефона. Например: +32 470 12 34 56.",
        },
        widget=forms.TextInput(attrs={
            "placeholder": "+32 470 12 34 56",
            "autocomplete": "tel",
            "maxlength": "40",
            "inputmode": "tel",
        }),
    )

    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={
            "autocomplete": "off",
            "tabindex": "-1",
        }),
    )

    class Meta:
        model = ContactMessage
        fields = [
            "name",
            "email",
            "phone",
            "telegram",
            "preferred_contact",
            "subject",
            "message",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Ваше имя",
                "autocomplete": "name",
                "maxlength": "120",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "email@example.com",
                "autocomplete": "email",
                "maxlength": "254",
            }),
            "telegram": forms.TextInput(attrs={
                "placeholder": "@username",
                "autocomplete": "off",
                "maxlength": "80",
            }),
            "preferred_contact": forms.Select(),
            "subject": forms.TextInput(attrs={
                "placeholder": "Например: хочу записаться на пробный урок",
                "maxlength": "180",
            }),
            "message": forms.Textarea(attrs={
                "placeholder": "Напишите, чем можем помочь",
                "rows": 5,
                "maxlength": "1500",
            }),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website", "").strip()

        if value:
            raise ValidationError("Ошибка отправки формы.")

        return value

    def clean_name(self):
        value = strip_tags(self.cleaned_data.get("name", "")).strip()
        value = re.sub(r"\s+", " ", value)

        if not NAME_RE.match(value):
            raise ValidationError("Введите корректное имя.")

        return value

    def clean_email(self):
        value = self.cleaned_data.get("email", "").strip().lower()

        if not value:
            return ""

        try:
            validate_email(value)
        except ValidationError:
            raise ValidationError("Введите корректный email.")

        if "\n" in value or "\r" in value:
            raise ValidationError("Email содержит недопустимые символы.")

        return value

    def clean_telegram(self):
        value = strip_tags(self.cleaned_data.get("telegram", "")).strip()
        value = value.replace("https://", "").replace("http://", "")
        value = value.replace("t.me/", "@").replace("telegram.me/", "@")
        value = re.sub(r"\s+", "", value)

        if not value:
            return ""

        if URL_RE.search(value):
            raise ValidationError("Укажите Telegram username, а не ссылку.")

        if not TELEGRAM_RE.match(value):
            raise ValidationError("Введите корректный Telegram username, например @username.")

        if not value.startswith("@"):
            value = f"@{value}"

        return value

    def clean_subject(self):
        value = strip_tags(self.cleaned_data.get("subject", "")).strip()
        value = re.sub(r"\s+", " ", value)

        if len(URL_RE.findall(value)) > 0:
            raise ValidationError("Тема не должна содержать ссылки.")

        return value

    def clean_message(self):
        value = strip_tags(self.cleaned_data.get("message", "")).strip()
        value = re.sub(r"\n{4,}", "\n\n\n", value)

        if len(value) < 10:
            raise ValidationError("Сообщение слишком короткое.")

        if len(value) > 1500:
            raise ValidationError("Сообщение слишком длинное.")

        if len(URL_RE.findall(value)) > 1:
            raise ValidationError("Слишком много ссылок в сообщении.")

        return value

    def clean(self):
        cleaned = super().clean()

        email = cleaned.get("email")
        phone = cleaned.get("phone")
        telegram = cleaned.get("telegram")
        preferred = cleaned.get("preferred_contact")

        if not email and not phone and not telegram:
            raise ValidationError("Укажите хотя бы один способ связи: email, телефон или Telegram.")

        if preferred == ContactMessage.CONTACT_EMAIL and not email:
            self.add_error("email", "Для связи по email нужно указать email.")

        if preferred == ContactMessage.CONTACT_PHONE and not phone:
            self.add_error("phone", "Для связи по телефону нужно указать корректный номер.")

        if preferred == ContactMessage.CONTACT_TELEGRAM and not telegram:
            self.add_error("telegram", "Для связи через Telegram нужно указать username.")

        return cleaned
