from django import forms
from config.i18n import bilingual as bt
from config.validators import clean_person_name
from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("name", "text")
        labels = {"name": bt("Your name", "Твоё имя"), "text": bt("Your review", "Твой отзыв")}
        widgets = {"text": forms.Textarea(attrs={"rows": 7, "maxlength": 3000})}

    def clean_name(self):
        return clean_person_name(self.cleaned_data["name"])
