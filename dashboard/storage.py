from __future__ import annotations

import csv
from pathlib import Path
from .config import Settings
from .weather import WeatherReport

HEADER = [
    "timestamp", "location", "temp_current", "feels_like", "temp_max", "temp_min",
    "humidity", "precip_percent", "wind_speed", "units",
]


def append_record(settings: Settings, report: WeatherReport) -> None:
    if not settings.csv_enabled:
        return
    settings.csv_file.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not settings.csv_file.exists() or settings.csv_file.stat().st_size == 0
    with settings.csv_file.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if needs_header:
            writer.writerow(HEADER)
        writer.writerow([
            report.observed_at.isoformat(), settings.location, report.temp_current, report.feels_like,
            report.temp_max, report.temp_min, report.humidity, report.precip_percent, report.wind,
            settings.units,
        ])
