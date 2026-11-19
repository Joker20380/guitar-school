from django.test import TestCase
from django.urls import reverse


class TunerPageTests(TestCase):
    def test_reference_pitch_switch_defaults_to_432_and_offers_440(self):
        response = self.client.get(reverse("tuner:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A4 = 432 Hz")
        self.assertContains(response, 'data-reference-pitch="432"')
        self.assertContains(response, 'data-reference-pitch="440"')
        self.assertContains(response, 'aria-pressed="true"')

    def test_microphone_sensitivity_controls_are_available(self):
        response = self.client.get(reverse("tuner:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="microphoneSensitivity"')
        self.assertContains(response, 'id="microphoneLevelFill"')

    def test_metronome_controls_and_script_are_available(self):
        response = self.client.get(reverse("tuner:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="metronomePanel"')
        self.assertContains(response, 'id="tempoInput"')
        self.assertContains(response, 'id="meterSelect"')
        self.assertContains(response, 'id="metronomeToggle"')
        self.assertContains(response, "Tap tempo")
        self.assertContains(response, "/static/tuner/js/metronome.")
