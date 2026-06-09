from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
from datetime import datetime

from dashboard.config import load_settings
from dashboard.dashboard_data import fetch_family_dashboard, sample_family_dashboard
from dashboard.display import update_display
from dashboard.lock import single_instance
from dashboard.render import render_dashboard
from dashboard.storage import append_record
from dashboard.weather import fetch_weather_data, process_weather_data, sample_weather


def configure_logging(log_file):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Update or preview the 7.5-inch Waveshare e-ink dashboard")
    parser.add_argument("--preview", action="store_true", help="Render PNG preview instead of touching hardware")
    parser.add_argument("--sample", action="store_true", help="Use built-in sample weather instead of OpenWeatherMap")
    parser.add_argument("--output", help="Preview output path; defaults to PREVIEW_FILE")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    configure_logging(settings.log_file)
    try:
        with single_instance(settings.lock_file):
            logging.info("Dashboard update started")
            report = sample_weather() if args.sample else process_weather_data(fetch_weather_data(settings))
            family = sample_family_dashboard() if args.sample else fetch_family_dashboard(settings)
            append_record(settings, report)
            image = render_dashboard(report, settings, now=datetime.now(), family=family)
            if args.preview:
                output = settings.project_root / args.output if args.output else settings.preview_file
                output.parent.mkdir(parents=True, exist_ok=True)
                image.save(output)
                logging.info("Preview written to %s", output)
            else:
                update_display(image)
            logging.info("Dashboard update finished")
        return 0
    except Exception:
        logging.exception("Dashboard update failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
