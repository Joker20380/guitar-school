"""Isolated local tests: no production database or outgoing email."""
from .settings import *  # noqa: F403

SECRET_KEY = "local-tests-only"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CONTACT_NOTIFY_EMAIL = ""
CONTACT_TELEGRAM = ""
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_NOTIFY_CHAT_ID = ""
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
