from django.utils.functional import lazy
from django.utils.translation import get_language


def text(english: str, russian: str) -> str:
    language = (get_language() or "en").split("-")[0]
    return russian if language == "ru" else english


bilingual = lazy(text, str)
