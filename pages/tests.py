from django.contrib.staticfiles import finders
from django.test import TestCase
from django.templatetags.static import static
from django.urls import reverse


class FaviconTests(TestCase):
    def test_public_and_admin_pages_link_the_provided_phoenix_icon(self):
        icon = static("images/branding/phoenix-emblem-60.webp")
        for language in ["en", "ru"]:
            self.client.cookies["phoenix_songs_language"] = language
            for route in ["/", "/tuner/", "/journal/", "/contacts/trial/", "/reviews/", "/admin/login/"]:
                with self.subTest(language=language, route=route):
                    self.assertContains(self.client.get(route), f'href="{icon}"')

    def test_conventional_favicon_url_redirects_to_an_existing_asset(self):
        asset = "images/branding/phoenix-emblem-60.webp"
        self.assertIsNotNone(finders.find(asset))
        response = self.client.get(reverse("pages:favicon"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, static(asset))
