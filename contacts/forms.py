import re
import unicodedata

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.html import strip_tags

from config.i18n import bilingual as bt
from phonenumber_field.formfields import PhoneNumberField

from .models import ContactMessage


URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)


class ContactMessageForm(forms.ModelForm):
    subject = forms.ChoiceField(
        label=bt("I would like to", "Хочу"),
        choices=[
            ("", bt("Choose an option", "Выберите вариант")),
            ("Online guitar lesson", bt("Book an online lesson", "Записаться на онлайн-урок")),
            ("Consultation", bt("Ask a question / consultation", "Задать вопрос / консультация")),
        ],
    )
    email = forms.EmailField(label=bt("Email", "Электронная почта"),
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "email@example.com"}))
    message = forms.CharField(required=False, max_length=1500,
        label=bt("Comment (optional)", "Комментарий (необязательно)"),
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": "1500"}))

    phone = PhoneNumberField(
        required=True,
        region="BE",
        label=bt('Phone', 'Телефон'),
        error_messages={
            "invalid": bt('Enter a valid phone number, for example +32 470 12 34 56.', 'Введите корректный номер телефона. Например: +32 470 12 34 56.'),
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
            "subject",
            "message",
        ]
        labels = {
            "name": bt("Name", "Имя"),
            "email": bt("Email", "Электронная почта"),
            "telegram": bt("Telegram", "Телеграм"),
            "preferred_contact": bt("Preferred contact", "Удобный способ связи"),
            "subject": bt("Subject", "Тема"),
            "message": bt("Message", "Сообщение"),
        }
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": bt('Your name', 'Ваше имя'),
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
                "placeholder": bt('For example: I would like to book a trial lesson', 'Например: хочу записаться на пробный урок'),
                "maxlength": "180",
            }),
            "message": forms.Textarea(attrs={
                "placeholder": bt('How can we help?', 'Напишите, чем можем помочь'),
                "rows": 5,
                "maxlength": "1500",
            }),
        }

    field_order = ["subject", "name", "email", "phone", "message", "website"]

    def clean_website(self):
        value = self.cleaned_data.get("website", "").strip()

        if value:
            raise ValidationError(bt('The form could not be submitted.', 'Ошибка отправки формы.'))

        return value

    def clean_name(self):
        value = strip_tags(self.cleaned_data.get("name", "")).strip()
        value = re.sub(r"\s+", " ", value)

        if not (1 <= len(value) <= 120) or not any(c.isalpha() for c in value) or any(
            not (c.isalpha() or unicodedata.category(c).startswith("M") or c in " '-’.") for c in value
        ):
            raise ValidationError(bt('Enter a valid name.', 'Введите корректное имя.'))

        return value

    def clean_email(self):
        value = self.cleaned_data.get("email", "").strip().lower()

        if not value:
            return ""

        try:
            validate_email(value)
        except ValidationError:
            raise ValidationError(bt('Enter a valid email address.', 'Введите корректный адрес электронной почты.'))

        if "\n" in value or "\r" in value:
            raise ValidationError(bt('The email address contains invalid characters.', 'Адрес электронной почты содержит недопустимые символы.'))

        return value

    def clean_subject(self):
        value = strip_tags(self.cleaned_data.get("subject", "")).strip()
        value = re.sub(r"\s+", " ", value)

        if len(URL_RE.findall(value)) > 0:
            raise ValidationError(bt('The subject must not contain links.', 'Тема не должна содержать ссылки.'))

        return value

    def clean_message(self):
        value = strip_tags(self.cleaned_data.get("message", "")).strip()
        value = re.sub(r"\n{4,}", "\n\n\n", value)

        if len(value) > 1500:
            raise ValidationError(bt('The message is too long.', 'Сообщение слишком длинное.'))

        if len(URL_RE.findall(value)) > 1:
            raise ValidationError(bt('The message contains too many links.', 'В сообщении слишком много ссылок.'))

        return value
