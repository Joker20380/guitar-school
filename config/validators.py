import unicodedata

from django.core.exceptions import ValidationError

from .i18n import bilingual as bt


def clean_person_name(value, max_length=120):
    value = unicodedata.normalize("NFC", value).strip()
    if (
        not 1 <= len(value) <= max_length
        or not any(character.isalpha() for character in value)
        or any(
            not (character.isalpha() or unicodedata.category(character).startswith("M")
                 or character in " '-’.")
            for character in value
        )
    ):
        raise ValidationError(bt("Enter a valid name.", "Введите корректное имя."))
    return " ".join(value.split())
