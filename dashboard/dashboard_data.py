from __future__ import annotations

from dataclasses import dataclass, field
import logging
import requests

from .config import Settings


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    date: str = ""
    time: str = ""


@dataclass(frozen=True)
class GroceryItem:
    title: str
    quantity: str = ""
    category: str = ""
    store: str = ""


@dataclass(frozen=True)
class FactBlock:
    title: str
    text: str


@dataclass(frozen=True)
class FamilyDashboard:
    calendar: list[CalendarEvent] = field(default_factory=list)
    grocery: list[GroceryItem] = field(default_factory=list)
    on_this_day: FactBlock | None = None
    random_fact: FactBlock | None = None


def sample_family_dashboard() -> FamilyDashboard:
    return FamilyDashboard(
        calendar=[
            CalendarEvent(summary="Mazda inspection", date="2026-06-02", time="8:00pm"),
            CalendarEvent(summary="Soccer practice", date="2026-06-03", time="6:00pm"),
            CalendarEvent(summary="Dentist appointment", date="2026-06-04", time="11:30am"),
        ],
        grocery=[
            GroceryItem(title="paper towels", quantity="2", category="household"),
            GroceryItem(title="bananas", category="produce"),
            GroceryItem(title="milk", quantity="1", category="dairy"),
            GroceryItem(title="dog food", category="pets"),
        ],
        on_this_day=FactBlock(title="On this day", text="1969 — Apollo 11 launched from Kennedy Space Center on its way to the Moon."),
        random_fact=FactBlock(title="Random fact", text="Honey never spoils; archaeologists have found edible honey in ancient tombs."),
    )


def _fact(data: dict | None) -> FactBlock | None:
    if not isinstance(data, dict):
        return None
    text = str(data.get("text") or "").strip()
    if not text:
        return None
    return FactBlock(title=str(data.get("title") or "Fact").strip() or "Fact", text=text)


def _parse_dashboard(data: dict) -> FamilyDashboard:
    calendar = [
        CalendarEvent(
            summary=str(event.get("summary") or "").strip(),
            date=str(event.get("date") or "").strip(),
            time=str(event.get("time") or "").strip(),
        )
        for event in data.get("calendar", [])
        if isinstance(event, dict) and str(event.get("summary") or "").strip()
    ]
    grocery = [
        GroceryItem(
            title=str(item.get("title") or "").strip(),
            quantity=str(item.get("quantity") or "").strip(),
            category=str(item.get("category") or "").strip(),
            store=str(item.get("store") or "").strip(),
        )
        for item in data.get("grocery", [])
        if isinstance(item, dict) and str(item.get("title") or "").strip()
    ]
    return FamilyDashboard(
        calendar=calendar,
        grocery=grocery,
        on_this_day=_fact(data.get("onThisDay")),
        random_fact=_fact(data.get("randomFact")),
    )


def fetch_family_dashboard(settings: Settings) -> FamilyDashboard:
    if not settings.dashboard_api_url:
        return FamilyDashboard()
    try:
        headers = {"User-Agent": "family-eink-dashboard/1.0"}
        if settings.eink_api_token:
            headers["x-eink-token"] = settings.eink_api_token
        response = requests.get(
            settings.dashboard_api_url,
            timeout=(settings.request_connect_timeout, settings.request_read_timeout),
            headers=headers,
        )
        response.raise_for_status()
        return _parse_dashboard(response.json())
    except Exception:
        logging.exception("Failed to fetch family dashboard data from %s", settings.dashboard_api_url)
        return FamilyDashboard()
