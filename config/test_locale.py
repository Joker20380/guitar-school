from django.test import SimpleTestCase, override_settings


@override_settings(ROOT_URLCONF="config.urls")
class PublicLocaleMiddlewareTests(SimpleTestCase):
    def test_browser_language_does_not_override_english_default(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="ru-RU,ru;q=0.9")
        self.assertEqual(response.headers["Content-Language"], "en")
        self.assertContains(response, "Individual guitar")

    def test_explicit_russian_cookie_is_respected(self):
        self.client.cookies["phoenix_songs_language"] = "ru"
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
        self.assertEqual(response.headers["Content-Language"], "ru")
        self.assertContains(response, "Индивидуальные уроки")
