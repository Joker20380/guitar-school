from .test_settings import *

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "phoenix_preview",
    "USER": "phoenix_test",
    "PASSWORD": "local-test-only",
    "HOST": "127.0.0.1",
    "PORT": "55439",
}}
MEDIA_ROOT = BASE_DIR / ".preview" / "media"
PRIVATE_MEDIA_ROOT = BASE_DIR / ".preview" / "private_media"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CONTACT_NOTIFY_EMAIL = ""
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_NOTIFY_CHAT_ID = ""
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
