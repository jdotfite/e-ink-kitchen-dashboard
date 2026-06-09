from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import Flask, jsonify, render_template, request

from dashboard.cache import (
    clear_reminder,
    get_family,
    get_meta,
    get_reminder,
    get_reminder_raw,
    get_weather_raw,
    set_family,
    set_last_display,
    set_reminder,
    set_weather_raw,
)
from dashboard.config import PROJECT_ROOT, load_settings
from dashboard.dashboard_data import fetch_family_dashboard
from dashboard.display import update_display
from dashboard.render import render_dashboard
from dashboard.storage import append_record
from dashboard.weather import fetch_weather_data, process_weather_data

app = Flask(__name__)
_display_lock = threading.Lock()
_scheduler = BackgroundScheduler()

SCHEDULE_FILE = PROJECT_ROOT / "data" / "schedules.json"
DEFAULT_SCHEDULE: dict = {
    "weather_interval_minutes": 15,
    "secondary_interval_minutes": 60,
}

log = logging.getLogger(__name__)


# ── Schedule persistence ──────────────────────────────────────────────────────

def _load_schedule() -> dict:
    try:
        if SCHEDULE_FILE.exists():
            loaded = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config = {**DEFAULT_SCHEDULE, **loaded}
                # Migrate old secondary_hours format
                config.pop("secondary_hours", None)
                return config
    except Exception:
        pass
    return dict(DEFAULT_SCHEDULE)


def _save_schedule(config: dict) -> None:
    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_FILE.write_text(json.dumps(config), encoding="utf-8")


# ── Core refresh logic ────────────────────────────────────────────────────────

def _render_and_display(settings, report, family, reminder) -> None:
    image = render_dashboard(report, settings, family=family, reminder=reminder)
    with _display_lock:
        update_display(image)
        set_last_display(datetime.now())


def _do_weather_refresh() -> None:
    try:
        settings = load_settings()
        raw = fetch_weather_data(settings)
        set_weather_raw(raw)
        report = process_weather_data(raw)
        append_record(settings, report)
        _render_and_display(settings, report, get_family(), get_reminder())
        log.info("Weather refresh complete")
    except Exception:
        log.exception("Weather refresh failed")


def _do_family_refresh() -> None:
    try:
        settings = load_settings()
        family = fetch_family_dashboard(settings)
        set_family(family)
        raw = get_weather_raw()
        if raw is None:
            log.warning("No cached weather; skipping display update after family refresh")
            return
        _render_and_display(settings, process_weather_data(raw), family, get_reminder())
        log.info("Family refresh complete")
    except Exception:
        log.exception("Family refresh failed")


def _do_all_refresh() -> None:
    try:
        settings = load_settings()
        raw = fetch_weather_data(settings)
        set_weather_raw(raw)
        report = process_weather_data(raw)
        append_record(settings, report)
        family = fetch_family_dashboard(settings)
        set_family(family)
        _render_and_display(settings, report, family, get_reminder())
        log.info("Full refresh complete")
    except Exception:
        log.exception("Full refresh failed")


def _do_render_only() -> None:
    """Re-render from cache without fetching — used when only the reminder changes."""
    try:
        settings = load_settings()
        raw = get_weather_raw()
        if raw is None:
            log.warning("No cached weather for render-only")
            return
        _render_and_display(settings, process_weather_data(raw), get_family(), get_reminder())
        log.info("Render-only complete")
    except Exception:
        log.exception("Render-only failed")


# ── Scheduler setup ───────────────────────────────────────────────────────────

def _setup_jobs(config: dict) -> None:
    _scheduler.remove_all_jobs()
    weather_interval = max(1, int(config.get("weather_interval_minutes", 15)))
    _scheduler.add_job(
        _do_weather_refresh,
        IntervalTrigger(minutes=weather_interval),
        id="weather",
        replace_existing=True,
    )
    family_interval = max(1, int(config.get("secondary_interval_minutes", 60)))
    _scheduler.add_job(
        _do_family_refresh,
        IntervalTrigger(minutes=family_interval),
        id="family",
        replace_existing=True,
    )
    log.info("Scheduler: weather every %d min; family every %d min", weather_interval, family_interval)


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    meta = get_meta()
    jobs = {j.id: j.next_run_time.isoformat() if j.next_run_time else None for j in _scheduler.get_jobs()}
    reminder_raw = meta.get("reminder")
    active_reminder = None
    if isinstance(reminder_raw, dict) and reminder_raw.get("text"):
        try:
            if datetime.fromisoformat(reminder_raw["expires_at"]) > datetime.now():
                active_reminder = reminder_raw
        except Exception:
            pass
    return jsonify({
        "weather_fetched_at": meta["weather_fetched_at"],
        "family_fetched_at": meta["family_fetched_at"],
        "last_display": meta["last_display"],
        "next_weather": jobs.get("weather"),
        "next_family": jobs.get("family"),
        "active_reminder": active_reminder,
    })


@app.route("/api/refresh/weather", methods=["POST"])
def api_refresh_weather():
    threading.Thread(target=_do_weather_refresh, daemon=True).start()
    return jsonify({"status": "refreshing"})


@app.route("/api/refresh/family", methods=["POST"])
def api_refresh_family():
    threading.Thread(target=_do_family_refresh, daemon=True).start()
    return jsonify({"status": "refreshing"})


@app.route("/api/refresh/all", methods=["POST"])
def api_refresh_all():
    threading.Thread(target=_do_all_refresh, daemon=True).start()
    return jsonify({"status": "refreshing"})


@app.route("/api/schedule", methods=["GET"])
def api_get_schedule():
    return jsonify(_load_schedule())


@app.route("/api/schedule", methods=["POST"])
def api_set_schedule():
    body = request.get_json(force=True) or {}
    config = _load_schedule()
    if "weather_interval_minutes" in body:
        val = int(body["weather_interval_minutes"])
        if not 1 <= val <= 1440:
            return jsonify({"error": "interval must be 1-1440 minutes"}), 400
        config["weather_interval_minutes"] = val
    if "secondary_interval_minutes" in body:
        val = int(body["secondary_interval_minutes"])
        if not 1 <= val <= 1440:
            return jsonify({"error": "interval must be 1-1440 minutes"}), 400
        config["secondary_interval_minutes"] = val
    _save_schedule(config)
    _setup_jobs(config)
    return jsonify(config)


@app.route("/api/reminder", methods=["GET"])
def api_get_reminder():
    r = get_reminder_raw()
    if not isinstance(r, dict):
        return jsonify(None)
    try:
        active = datetime.fromisoformat(r["expires_at"]) > datetime.now()
    except Exception:
        active = False
    return jsonify({**r, "active": active})


@app.route("/api/reminder", methods=["POST"])
def api_set_reminder():
    body = request.get_json(force=True) or {}
    text = str(body.get("text", "")).strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    title = str(body.get("title", "Reminder")).strip() or "Reminder"
    try:
        if "expires_at" in body:
            expires_at = datetime.fromisoformat(body["expires_at"])
        elif "duration_hours" in body:
            expires_at = datetime.now() + timedelta(hours=float(body["duration_hours"]))
        else:
            return jsonify({"error": "provide expires_at or duration_hours"}), 400
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    set_reminder(title, text, expires_at)
    threading.Thread(target=_do_render_only, daemon=True).start()
    return jsonify({"status": "set", "expires_at": expires_at.isoformat()})


@app.route("/api/reminder", methods=["DELETE"])
def api_clear_reminder():
    clear_reminder()
    threading.Thread(target=_do_render_only, daemon=True).start()
    return jsonify({"status": "cleared"})


@app.route("/api/deploy", methods=["POST"])
def api_deploy():
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=60,
        )
        output = (result.stdout + result.stderr).strip()
        changed = result.returncode == 0 and "Already up to date" not in output
        if changed:
            # Exit cleanly — systemd Restart=on-failure brings the process back up with new code
            threading.Thread(target=lambda: (
                __import__("time").sleep(1), os._exit(0)
            ), daemon=True).start()
        return jsonify({"output": output or "Already up to date.", "restarting": changed})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        handlers=[
            RotatingFileHandler(log_dir / "server.log", maxBytes=1_000_000, backupCount=3),
            logging.StreamHandler(),
        ],
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config = _load_schedule()
    _setup_jobs(config)
    _scheduler.start()
    threading.Thread(target=_do_all_refresh, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
