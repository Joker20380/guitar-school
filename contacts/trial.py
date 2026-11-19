import logging
import re
import uuid

from django import forms
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from phonenumber_field.formfields import PhoneNumberField

from config.i18n import bilingual as bt
from config.validators import clean_person_name
from .models import ContactMessage
from .notifications import notify_trial

logger = logging.getLogger(__name__)
TOKEN_SALT = "phoenix-trial-submission-v1"


def saved_response(request):
    request.session["trial_success"] = True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"saved": True, "redirect": reverse("contacts:trial_success")})
    return redirect("contacts:trial_success")


class TrialForm(forms.ModelForm):
    direction = forms.ChoiceField(label=bt("Direction", "Направление"), choices=[("", bt("Choose a direction", "Выберите направление"))] + ContactMessage.DIRECTION_CHOICES)
    phone = PhoneNumberField(region=None, label=bt("Phone with country code", "Телефон с кодом страны"), widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel", "placeholder": "+44 20 7946 0958", "maxlength": 40, "aria-describedby": "phone-help"}))
    preferred_contact = forms.ChoiceField(required=False, initial="whatsapp", label=bt("Preferred contact", "Удобный способ связи"), choices=[("whatsapp", "WhatsApp"), ("telegram", "Telegram"), ("other", bt("Another way", "Другой способ"))])
    submission_token = forms.CharField(widget=forms.HiddenInput)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = ContactMessage
        fields = ["name", "direction", "phone", "preferred_contact", "telegram", "other_contact"]
        labels = {"name": bt("Name", "Имя"), "telegram": bt("Telegram username (optional)", "Ник в Telegram (необязательно)"), "other_contact": bt("Tell us how you'd prefer to be contacted", "Укажи удобный способ связи")}
        widgets = {"name": forms.TextInput(attrs={"autocomplete": "name"}), "telegram": forms.TextInput(attrs={"placeholder": "@username"}), "other_contact": forms.TextInput(attrs={"aria-describedby": "other-contact-help"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        channel = self.data.get("preferred_contact", "whatsapp") if self.is_bound else "whatsapp"
        for field, applicable in [("telegram", "telegram"), ("other_contact", "other")]:
            if channel != applicable:
                self.fields[field].disabled = True
        for field in self.fields.values():
            field.error_messages["required"] = bt("Please fill in this field.", "Заполните это поле.")
        self.fields["direction"].error_messages["invalid_choice"] = bt("Choose one of the listed directions.", "Выберите направление из списка.")

    def clean_name(self):
        return clean_person_name(self.cleaned_data["name"])

    def clean_phone(self):
        if not self.data.get("phone", "").strip().startswith("+"):
            raise ValidationError(bt("Include + and your country code.", "Укажите + и код страны."))
        return self.cleaned_data["phone"]

    def clean_preferred_contact(self):
        return self.cleaned_data.get("preferred_contact") or "whatsapp"

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError(bt("Unable to submit this form.", "Не удалось отправить форму."))
        return ""

    def clean_telegram(self):
        value = self.cleaned_data.get("telegram", "").strip()
        if value and not re.fullmatch(r"@?[A-Za-z][A-Za-z0-9_]{4,31}", value):
            raise ValidationError(bt("Use a Telegram username such as @username.", "Укажите ник Telegram, например @username."))
        return "@" + value.lstrip("@") if value else ""

    def clean_other_contact(self):
        value = self.cleaned_data.get("other_contact", "").strip()
        if value and (any(ord(character) < 32 for character in value) or any(character in value for character in "<>")):
            raise ValidationError(bt("Enter plain contact details, without markup.", "Укажите контакт без HTML-разметки."))
        return value


def trial_page(request):
    response_status = 400
    session_marker = request.session.get("trial_session_marker")
    if not session_marker:
        session_marker = uuid.uuid4().hex
        request.session["trial_session_marker"] = session_marker
    if request.method == "POST":
        form = TrialForm(request.POST)
        if form.is_valid():
            try:
                payload = signing.loads(form.cleaned_data["submission_token"], salt=TOKEN_SALT, max_age=7200)
                if payload["session"] != session_marker:
                    raise signing.BadSignature()
                submission_key = uuid.UUID(payload["key"])
            except (signing.BadSignature, KeyError, ValueError, TypeError):
                form.add_error(None, bt("This form has expired. Reload the page and try again.", "Срок действия формы истёк. Обновите страницу и повторите попытку."))
            else:
                try:
                    existing = ContactMessage.objects.filter(submission_key=submission_key).first()
                    if existing:
                        return saved_response(request)
                    last_sent = request.session.get("trial_last_sent", 0)
                    if timezone.now().timestamp() - last_sent < 30:
                        form.add_error(None, bt("Please wait 30 seconds before a new request.", "Подождите 30 секунд перед новой заявкой."))
                    else:
                        values = {field: form.cleaned_data[field] for field in form.Meta.fields}
                        with transaction.atomic():
                            entry, created = ContactMessage.objects.get_or_create(submission_key=submission_key, defaults={**values, "subject": "Trial lesson", "message": ""})
                        if created:
                            notify_trial(entry)
                        request.session["trial_last_sent"] = timezone.now().timestamp()
                        return saved_response(request)
                except DatabaseError:
                    response_status = 503
                    logger.warning("Trial persistence failed")
                    form.add_error(None, bt("We could not save your request. Your details are still here; please try again.", "Не удалось сохранить заявку. Ваши данные остались в форме; попробуйте ещё раз."))
    else:
        direction = request.GET.get("direction", "")
        if direction not in dict(ContactMessage.DIRECTION_CHOICES):
            direction = ""
        token = signing.dumps({"key": uuid.uuid4().hex, "session": session_marker}, salt=TOKEN_SALT)
        form = TrialForm(initial={"direction": direction, "submission_token": token})
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"saved": False, "errors": form.errors.get_json_data()}, status=response_status)
    return render(request, "contacts/trial.html", {"form": form})


def trial_success(request):
    if not request.session.get("trial_success"):
        return redirect("contacts:trial")
    return render(request, "contacts/trial_success.html")
