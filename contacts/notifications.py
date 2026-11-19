import json
import logging
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_telegram(text):
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    recipient = getattr(settings, "TELEGRAM_NOTIFY_CHAT_ID", "")
    if not token or not recipient:
        return "disabled"
    payload = json.dumps({"chat_id": recipient, "text": text}).encode()
    request = Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        return "accepted" if json.load(response).get("ok") is True else "failed"


def notify_trial(entry):
    body = f"Phoenix Song: пробный урок\nИмя: {entry.name}\nНаправление: {entry.get_direction_display()}\nТелефон: {entry.phone}\nСпособ связи: {entry.get_preferred_contact_display()}\nTelegram: {entry.telegram}\nДругой контакт: {entry.other_contact}"
    recipient = getattr(settings, "CONTACT_NOTIFY_EMAIL", "")
    email_state = "disabled"
    telegram_state = "disabled"
    if recipient:
        try:
            accepted = send_mail("Phoenix Song: заявка", body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
            email_state = "accepted" if accepted == 1 else "failed"
        except Exception:
            email_state = "failed"
    try:
        telegram_state = send_telegram(body)
    except Exception:
        telegram_state = "failed"
    try:
        type(entry).objects.filter(pk=entry.pk).update(email_notification_status=email_state, telegram_notification_status=telegram_state)
    except Exception:
        logger.warning("Could not persist notification outcome for trial %s", entry.pk)
