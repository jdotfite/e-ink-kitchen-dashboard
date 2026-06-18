from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
import logging
import requests

from .config import Settings


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    date: str = ""
    time: str = ""


@dataclass(frozen=True)
class StockQuote:
    ticker: str
    price: float
    change_pct: float


@dataclass(frozen=True)
class FactBlock:
    title: str
    text: str


@dataclass(frozen=True)
class FamilyDashboard:
    calendar: list[CalendarEvent] = field(default_factory=list)
    stocks: list[StockQuote] = field(default_factory=list)
    on_this_day: FactBlock | None = None
    random_fact: FactBlock | None = None


def sample_family_dashboard() -> FamilyDashboard:
    return FamilyDashboard(
        calendar=[
            CalendarEvent(summary="Mazda inspection", date="2026-06-02", time="8:00pm"),
            CalendarEvent(summary="Soccer practice", date="2026-06-03", time="6:00pm"),
            CalendarEvent(summary="Dentist appointment", date="2026-06-04", time="11:30am"),
        ],
        stocks=[
            StockQuote(ticker="AAPL", price=192.34, change_pct=1.2),
            StockQuote(ticker="MSFT", price=415.20, change_pct=-0.3),
            StockQuote(ticker="GOOG", price=178.45, change_pct=0.8),
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


def _parse_api_response(data: dict) -> tuple[list[CalendarEvent], FactBlock | None, FactBlock | None]:
    calendar = [
        CalendarEvent(
            summary=str(event.get("summary") or "").strip(),
            date=str(event.get("date") or "").strip(),
            time=str(event.get("time") or "").strip(),
        )
        for event in data.get("calendar", [])
        if isinstance(event, dict) and str(event.get("summary") or "").strip()
    ]
    return calendar, _fact(data.get("onThisDay")), _fact(data.get("randomFact"))


def _fetch_calendar_ical(ical_url: str, settings: Settings) -> list[CalendarEvent]:
    try:
        from icalendar import Calendar
        import recurring_ical_events
    except ImportError:
        logging.warning("icalendar/recurring-ical-events not installed; skipping iCal calendar")
        return []
    try:
        response = requests.get(
            ical_url,
            timeout=(settings.request_connect_timeout, settings.request_read_timeout),
            headers={"User-Agent": "family-eink-dashboard/1.0"},
        )
        response.raise_for_status()
        cal = Calendar.from_ical(response.content)
        today = date.today()
        end = today + timedelta(days=60)
        raw_events = recurring_ical_events.of(cal).between(today, end)
        events: list[tuple[date, str, str]] = []
        for event in raw_events:
            dtstart = event.get("DTSTART")
            if dtstart is None:
                continue
            dt = dtstart.dt
            summary = str(event.get("SUMMARY", "")).strip()
            if not summary:
                continue
            if isinstance(dt, datetime):
                event_date = dt.date()
                time_str = dt.strftime("%I:%M %p").lstrip("0")
            else:
                event_date = dt
                time_str = ""
            events.append((event_date, time_str, summary))
        events.sort(key=lambda e: e[0])
        return [
            CalendarEvent(summary=s, date=d.isoformat(), time=t)
            for d, t, s in events[:8]
        ]
    except Exception:
        logging.exception("Failed to fetch iCal calendar from %s", ical_url[:80])
        return []


def _fetch_stocks(tickers: tuple[str, ...]) -> list[StockQuote]:
    if not tickers:
        return []
    try:
        import yfinance as yf
    except ImportError:
        logging.warning("yfinance not installed; skipping stocks")
        return []
    results: list[StockQuote] = []
    for symbol in tickers[:4]:
        try:
            info = yf.Ticker(symbol).fast_info
            price = float(info.last_price)
            prev = float(info.previous_close)
            change_pct = (price - prev) / prev * 100 if prev else 0.0
            results.append(StockQuote(ticker=symbol, price=price, change_pct=change_pct))
        except Exception:
            logging.exception("Failed to fetch stock quote for %s", symbol)
    return results


def fetch_family_dashboard(settings: Settings) -> FamilyDashboard:
    calendar: list[CalendarEvent] = []
    on_this_day: FactBlock | None = None
    random_fact: FactBlock | None = None

    if settings.google_calendar_ical_url:
        calendar = _fetch_calendar_ical(settings.google_calendar_ical_url, settings)

    if settings.dashboard_api_url:
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
            api_cal, on_this_day, random_fact = _parse_api_response(response.json())
            if not calendar:
                calendar = api_cal
        except Exception:
            logging.exception("Failed to fetch dashboard data from %s", settings.dashboard_api_url)

    stocks = _fetch_stocks(settings.stock_tickers)

    return FamilyDashboard(
        calendar=calendar,
        stocks=stocks,
        on_this_day=on_this_day,
        random_fact=random_fact,
    )
