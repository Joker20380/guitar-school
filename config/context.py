from urllib.parse import urlparse

from django.conf import settings


def public_contacts(request):
    telegram = getattr(settings, "CONTACT_TELEGRAM", "")
    parsed = urlparse(telegram)
    if parsed.scheme != "https" or parsed.netloc != "t.me" or not parsed.path.strip("/"):
        telegram = ""
    return {"public_phone": "+7 916 171 2233", "public_email": "Phoenixsong.school@gmail.com", "public_telegram": telegram}
