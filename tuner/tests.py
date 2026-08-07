from django.test import TestCase
from django.urls import reverse


class TunerPageTests(TestCase):
    def test_reference_pitch_switch_defaults_to_432_and_offers_440(self):
        response = self.client.get(reverse("tuner:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A4 = 432 Гц")
        self.assertContains(response, 'data-reference-pitch="432"')
        self.assertContains(response, 'data-reference-pitch="440"')
        self.assertContains(response, 'aria-pressed="true"')
