import unittest
from pathlib import Path
from datetime import datetime

from dashboard.config import load_settings
from dashboard.render import render_dashboard, WIDTH, HEIGHT
from dashboard.weather import sample_weather


class RenderTests(unittest.TestCase):
    def test_sample_render_is_display_size_and_1bit(self):
        settings = load_settings(Path('.env.example'))
        image = render_dashboard(sample_weather(), settings, now=datetime(2026, 6, 2, 9, 0))
        self.assertEqual(image.size, (WIDTH, HEIGHT))
        self.assertEqual(image.mode, '1')

    def test_long_weather_description_still_renders(self):
        settings = load_settings(Path('.env.example'))
        report = sample_weather()
        report = report.__class__(**{**report.__dict__, 'description': 'Partly Cloudy With A Very Long Description That Would Normally Overflow'})
        image = render_dashboard(report, settings, now=datetime(2026, 6, 2, 9, 0))
        self.assertEqual(image.size, (800, 480))


if __name__ == '__main__':
    unittest.main()
