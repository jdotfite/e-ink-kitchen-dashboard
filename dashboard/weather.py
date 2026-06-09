from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

import requests

from .config import Settings, validate_for_live_weather

BASE_URL = "https://api.openweathermap.org/data/3.0/onecall"


@dataclass(frozen=True)
class ForecastDay:
    label: str
    icon_code: str
    temp_max: float
    temp_min: float
    precip_percent: float


@dataclass(frozen=True)
class WeatherReport:
    temp_current: float
    feels_like: float
    humidity: int
    wind: float
    description: str
    icon_code: str
    temp_max: float
    temp_min: float
    precip_percent: float
    observed_at: datetime
    forecast: tuple[ForecastDay, ...] = ()


def _redact_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([(k, "REDACTED" if k == "appid" else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def build_url(settings: Settings) -> str:
    params = {
        "lat": settings.latitude,
        "lon": settings.longitude,
        "units": settings.units,
        "exclude": "minutely,hourly,alerts",
        "appid": settings.api_key,
    }
    return f"{BASE_URL}?{urlencode(params)}"


def fetch_weather_data(settings: Settings) -> dict:
    validate_for_live_weather(settings)
    url = build_url(settings)
    try:
        response = requests.get(url, timeout=(settings.request_connect_timeout, settings.request_read_timeout))
        response.raise_for_status()
        logging.info("Weather data fetched successfully from %s", _redact_url(url))
        return response.json()
    except requests.RequestException as exc:
        logging.error("Weather request failed for %s: %s", _redact_url(url), exc.__class__.__name__)
        raise


def _forecast_days(data: dict) -> tuple[ForecastDay, ...]:
    labels = ["Today", "Tomorrow"]
    days: list[ForecastDay] = []
    for idx, daily in enumerate(data.get("daily", [])[:3]):
        if idx < len(labels):
            label = labels[idx]
        else:
            label = datetime.fromtimestamp(int(daily.get("dt", 0)), tz=timezone.utc).strftime("%a")
        weather = (daily.get("weather") or [{}])[0]
        days.append(ForecastDay(
            label=label,
            icon_code=str(weather.get("icon") or "01d"),
            temp_max=float(daily.get("temp", {}).get("max", 0)),
            temp_min=float(daily.get("temp", {}).get("min", 0)),
            precip_percent=float(daily.get("pop", 0)) * 100,
        ))
    return tuple(days)


def process_weather_data(data: dict) -> WeatherReport:
    current = data["current"]
    daily = data["daily"][0]
    return WeatherReport(
        temp_current=float(current["temp"]),
        feels_like=float(current["feels_like"]),
        humidity=int(current["humidity"]),
        wind=float(current["wind_speed"]),
        description=str(current["weather"][0]["description"]).title(),
        icon_code=str(current["weather"][0]["icon"]),
        temp_max=float(daily["temp"]["max"]),
        temp_min=float(daily["temp"]["min"]),
        precip_percent=float(daily.get("pop", 0)) * 100,
        observed_at=datetime.fromtimestamp(int(current.get("dt", datetime.now(timezone.utc).timestamp())), tz=timezone.utc),
        forecast=_forecast_days(data),
    )


def sample_weather() -> WeatherReport:
    return WeatherReport(
        temp_current=72,
        feels_like=74,
        humidity=55,
        wind=8.2,
        description="Partly Cloudy",
        icon_code="02d",
        temp_max=81,
        temp_min=64,
        precip_percent=30,
        observed_at=datetime.now(timezone.utc),
        forecast=(
            ForecastDay("Today", "02d", 81, 64, 30),
            ForecastDay("Tomorrow", "10d", 78, 61, 70),
            ForecastDay("Thu", "04d", 74, 58, 15),
        ),
    )
