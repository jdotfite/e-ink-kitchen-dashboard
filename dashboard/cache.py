from __future__ import annotations

import json
import threading
from datetime import datetime

from .config import PROJECT_ROOT
from .dashboard_data import CalendarEvent, FactBlock, FamilyDashboard, GroceryItem

_CACHE_FILE = PROJECT_ROOT / "data" / "cache.json"
_lock = threading.Lock()


def _load() -> dict:
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save(data: dict) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(data, default=str), encoding="utf-8")


# ── Weather ───────────────────────────────────────────────────────────────────

def get_weather_raw() -> dict | None:
    with _lock:
        return _load().get("weather", {}).get("raw")


def set_weather_raw(raw: dict) -> None:
    with _lock:
        data = _load()
        data.setdefault("weather", {})["raw"] = raw
        data["weather"]["fetched_at"] = datetime.now().isoformat()
        _save(data)


# ── Family ────────────────────────────────────────────────────────────────────

def get_family() -> FamilyDashboard:
    with _lock:
        d = _load().get("family")
    if not isinstance(d, dict):
        return FamilyDashboard()
    try:
        return FamilyDashboard(
            calendar=[CalendarEvent(**e) for e in (d.get("calendar") or [])],
            grocery=[GroceryItem(**g) for g in (d.get("grocery") or [])],
            on_this_day=FactBlock(**d["on_this_day"]) if d.get("on_this_day") else None,
            random_fact=FactBlock(**d["random_fact"]) if d.get("random_fact") else None,
        )
    except Exception:
        return FamilyDashboard()


def set_family(family: FamilyDashboard) -> None:
    with _lock:
        data = _load()
        data["family"] = {
            "calendar": [{"summary": e.summary, "date": e.date, "time": e.time} for e in family.calendar],
            "grocery": [
                {"title": g.title, "quantity": g.quantity, "category": g.category, "store": g.store}
                for g in family.grocery
            ],
            "on_this_day": {"title": family.on_this_day.title, "text": family.on_this_day.text}
            if family.on_this_day else None,
            "random_fact": {"title": family.random_fact.title, "text": family.random_fact.text}
            if family.random_fact else None,
            "fetched_at": datetime.now().isoformat(),
        }
        _save(data)


# ── Reminder ──────────────────────────────────────────────────────────────────

def get_reminder() -> FactBlock | None:
    with _lock:
        r = _load().get("reminder")
    if not isinstance(r, dict) or not r.get("text"):
        return None
    try:
        if datetime.fromisoformat(r["expires_at"]) <= datetime.now():
            return None
    except (KeyError, ValueError):
        return None
    return FactBlock(title=r.get("title", "Reminder") or "Reminder", text=r["text"])


def get_reminder_raw() -> dict | None:
    with _lock:
        return _load().get("reminder")


def set_reminder(title: str, text: str, expires_at: datetime) -> None:
    with _lock:
        data = _load()
        data["reminder"] = {"title": title, "text": text, "expires_at": expires_at.isoformat()}
        _save(data)


def clear_reminder() -> None:
    with _lock:
        data = _load()
        data.pop("reminder", None)
        _save(data)


# ── Misc ──────────────────────────────────────────────────────────────────────

def set_last_display(dt: datetime) -> None:
    with _lock:
        data = _load()
        data["last_display"] = dt.isoformat()
        _save(data)


def get_meta() -> dict:
    with _lock:
        data = _load()
    return {
        "weather_fetched_at": data.get("weather", {}).get("fetched_at"),
        "family_fetched_at": data.get("family", {}).get("fetched_at"),
        "last_display": data.get("last_display"),
        "reminder": data.get("reminder"),
    }
