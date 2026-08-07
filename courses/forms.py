import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.html import strip_tags
from phonenumber_field.formfields import PhoneNumberField

from .models import CourseRequest, Teacher, TeacherAssignment, TeacherRequest


URL_RE = re.compile(r"https?://|www\.|\.ru|\.com|\.net|\.org", re.IGNORECASE)
NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁёІіЇїЄє'\-\s]{2,80}$")
MESSENGER_RE = re.compile(r"^@?[A-Za-z0-9_][A-Za-z0-9_.\-]{2,78}$")


class CourseRequestForm(forms.ModelForm):
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
        model = CourseRequest
        fields = [
            "name",
            "phone",
            "messenger",
            "email",
            "verification_channel",
            "preferred_format",
            "message",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Ваше имя",
                "autocomplete": "name",
                "maxlength": "120",
            }),
            "messenger": forms.TextInput(attrs={
                "placeholder": "@telegram или другой ник без ссылки",
                "autocomplete": "off",
                "maxlength": "80",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "email@example.com",
                "autocomplete": "email",
                "maxlength": "254",
            }),
            "verification_channel": forms.Select(),
            "preferred_format": forms.Select(),
            "message": forms.Textarea(attrs={
                "placeholder": "Расскажите, какой у вас уровень и чему хотите научиться",
                "rows": 4,
                "maxlength": "1000",
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

        if URL_RE.search(value):
            raise ValidationError("Имя не должно содержать ссылки.")

        return value

    def clean_messenger(self):
        value = strip_tags(self.cleaned_data.get("messenger", "")).strip()
        value = value.replace("https://", "").replace("http://", "")
        value = value.replace("t.me/", "@").replace("telegram.me/", "@")
        value = re.sub(r"\s+", "", value)

        if not value:
            return ""

        if URL_RE.search(value):
            raise ValidationError("Укажите ник в мессенджере, а не ссылку.")

        if not MESSENGER_RE.match(value):
            raise ValidationError("Введите корректный ник мессенджера, например @username.")

        if not value.startswith("@"):
            value = f"@{value}"

        return value

    def clean_email(self):
        value = self.cleaned_data.get("email", "").strip().lower()

        if not value:
            return ""

        # Email проверяем только штатным валидатором Django.
        # Нельзя прогонять email через URL_RE, потому что нормальные домены
        # gmail.com, mail.ru, outlook.com и т.д. будут ошибочно отклоняться.
        try:
            validate_email(value)
        except ValidationError:
            raise ValidationError("Введите корректный email.")

        if "\n" in value or "\r" in value:
            raise ValidationError("Email содержит недопустимые символы.")

        return value

    def clean_message(self):
        value = strip_tags(self.cleaned_data.get("message", "")).strip()
        value = re.sub(r"\n{4,}", "\n\n\n", value)

        if len(value) > 1000:
            raise ValidationError("Комментарий слишком длинный.")

        if len(URL_RE.findall(value)) > 1:
            raise ValidationError("Слишком много ссылок в сообщении.")

        return value

    def clean(self):
        cleaned = super().clean()

        channel = cleaned.get("verification_channel")
        email = cleaned.get("email")
        phone = cleaned.get("phone")
        messenger = cleaned.get("messenger")

        if not email and not phone and not messenger:
            raise ValidationError("Укажите хотя бы один способ связи: email, телефон или мессенджер.")

        if channel == CourseRequest.VERIFY_EMAIL and not email:
            self.add_error("email", "Для подтверждения по email нужно указать email.")

        if channel == CourseRequest.VERIFY_PHONE and not phone:
            self.add_error("phone", "Для подтверждения по телефону нужно указать корректный номер.")

        if channel == CourseRequest.VERIFY_MESSENGER and not messenger and not phone:
            self.add_error("messenger", "Укажите мессенджер или телефон для подтверждения.")

        return cleaned


class TeacherRequestForm(forms.ModelForm):
    class Meta:
        model = TeacherRequest
        fields = ["request_type", "current_teacher", "requested_teacher", "message"]
        widgets = {
            "request_type": forms.Select(),
            "current_teacher": forms.Select(),
            "requested_teacher": forms.Select(),
            "message": forms.Textarea(attrs={
                "placeholder": "Напишите, почему хотите заниматься с этим преподавателем или сменить текущего",
                "rows": 4,
                "maxlength": "1000",
            }),
        }

    def __init__(self, *args, enrollment=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.enrollment = enrollment

        self.fields["requested_teacher"].queryset = Teacher.objects.filter(is_active=True).order_by(
            "sort_order",
            "full_name",
        )
        self.fields["requested_teacher"].required = False
        self.fields["requested_teacher"].empty_label = "Выберите преподавателя"

        current_teacher_ids = []

        if enrollment:
            current_teacher_ids = list(
                TeacherAssignment.objects
                .filter(enrollment=enrollment, is_active=True, teacher__is_active=True)
                .values_list("teacher_id", flat=True)
            )

        self.fields["current_teacher"].queryset = Teacher.objects.filter(id__in=current_teacher_ids).order_by(
            "sort_order",
            "full_name",
        )
        self.fields["current_teacher"].required = False
        self.fields["current_teacher"].empty_label = "Текущий преподаватель"

    def clean_message(self):
        value = strip_tags(self.cleaned_data.get("message", "")).strip()
        value = re.sub(r"\n{4,}", "\n\n\n", value)

        if len(value) > 1000:
            raise ValidationError("Комментарий слишком длинный.")

        return value

    def clean(self):
        cleaned = super().clean()

        request_type = cleaned.get("request_type")
        current_teacher = cleaned.get("current_teacher")
        requested_teacher = cleaned.get("requested_teacher")

        if not requested_teacher:
            self.add_error("requested_teacher", "Выберите преподавателя.")

        if request_type == TeacherRequest.TYPE_CHANGE:
            has_current_teachers = False

            if self.enrollment:
                has_current_teachers = TeacherAssignment.objects.filter(
                    enrollment=self.enrollment,
                    is_active=True,
                    teacher__is_active=True,
                ).exists()

            if has_current_teachers and not current_teacher:
                self.add_error("current_teacher", "Выберите текущего преподавателя для замены.")

        if current_teacher and requested_teacher and current_teacher == requested_teacher:
            self.add_error("requested_teacher", "Новый преподаватель должен отличаться от текущего.")

        return cleaned
