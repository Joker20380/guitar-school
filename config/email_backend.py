import json
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address


class BrevoEmailBackend(BaseEmailBackend):
    """Django email backend for Brevo's HTTPS transactional API."""

    endpoint = "https://api.brevo.com/v3/smtp/email"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "BREVO_API_KEY", "").strip()
        if not api_key:
            if self.fail_silently:
                return 0
            raise RuntimeError("BREVO_API_KEY is not configured")

        sent = 0
        for message in email_messages:
            try:
                self._send(message, api_key)
            except Exception:
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def _send(self, message, api_key):
        payload = self._payload(message)
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=getattr(settings, "BREVO_API_TIMEOUT", 10),
            ) as response:
                if response.status != 201:
                    raise RuntimeError(f"Brevo returned HTTP {response.status}")
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Brevo returned HTTP {error.code}: {details}") from error
        except URLError as error:
            raise RuntimeError(f"Brevo API connection failed: {error.reason}") from error

    def _payload(self, message):
        from_email = message.from_email or settings.DEFAULT_FROM_EMAIL
        from_name, from_address = parseaddr(sanitize_address(from_email, message.encoding))
        payload = {
            "sender": {"email": from_address},
            "to": [self._recipient(address, message.encoding) for address in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }
        if from_name:
            payload["sender"]["name"] = from_name

        html_body = next(
            (alternative.content for alternative in getattr(message, "alternatives", ()) if alternative.mimetype == "text/html"),
            None,
        )
        if html_body:
            payload["htmlContent"] = html_body

        if message.cc:
            payload["cc"] = [self._recipient(address, message.encoding) for address in message.cc]
        if message.bcc:
            payload["bcc"] = [self._recipient(address, message.encoding) for address in message.bcc]

        reply_to = message.reply_to or getattr(settings, "BREVO_REPLY_TO", "")
        if reply_to:
            payload["replyTo"] = self._recipient(
                reply_to[0] if isinstance(reply_to, (list, tuple)) else reply_to,
                message.encoding,
            )
        return payload

    @staticmethod
    def _recipient(address, encoding):
        name, email = parseaddr(sanitize_address(address, encoding))
        recipient = {"email": email}
        if name:
            recipient["name"] = name
        return recipient
