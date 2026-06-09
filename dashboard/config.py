from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _get(env_file: dict[str, str], key: str, default: str = "") -> str:
    return os.environ.get(key, env_file.get(key, default))


def _bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _int_list(value: str) -> list[int]:
    if not value.strip():
        return []
    days: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        day = int(part)
        if not 0 <= day <= 6:
            raise ValueError(f"Trash day must be 0-6, got {day}")
        days.append(day)
    return days


@dataclass(frozen=True)
class Settings:
    project_root: Path
    api_key: str
    latitude: str
    longitude: str
    location: str = "Home"
    units: str = "imperial"
    request_connect_timeout: float = 5.0
    request_read_timeout: float = 20.0
    trash_days: tuple[int, ...] = ()
    csv_enabled: bool = True
    log_file: Path = PROJECT_ROOT / "logs" / "dashboard.log"
    csv_file: Path = PROJECT_ROOT / "data" / "records.csv"
    preview_file: Path = PROJECT_ROOT / "output" / "preview.png"
    lock_file: Path = PROJECT_ROOT / "dashboard.lock"
    dashboard_api_url: str = ""
    eink_api_token: str = ""

    @property
    def temp_unit(self) -> str:
        return {"imperial": "°F", "metric": "°C", "standard": "K"}.get(self.units, "°F")

    @property
    def wind_unit(self) -> str:
        return {"imperial": "MPH", "metric": "m/s", "standard": "m/s"}.get(self.units, "MPH")


def load_settings(env_path: Path | None = None) -> Settings:
    env_path = env_path or PROJECT_ROOT / ".env"
    env_file = _load_env_file(env_path)
    units = _get(env_file, "OPENWEATHER_UNITS", "imperial").lower()
    if units not in {"imperial", "metric", "standard"}:
        raise ValueError("OPENWEATHER_UNITS must be imperial, metric, or standard")
    return Settings(
        project_root=PROJECT_ROOT,
        api_key=_get(env_file, "OPENWEATHER_API_KEY"),
        latitude=_get(env_file, "OPENWEATHER_LATITUDE"),
        longitude=_get(env_file, "OPENWEATHER_LONGITUDE"),
        location=_get(env_file, "DASHBOARD_LOCATION", "Home"),
        units=units,
        request_connect_timeout=float(_get(env_file, "REQUEST_CONNECT_TIMEOUT", "5")),
        request_read_timeout=float(_get(env_file, "REQUEST_READ_TIMEOUT", "20")),
        trash_days=tuple(_int_list(_get(env_file, "TRASH_DAYS", ""))),
        csv_enabled=_bool(_get(env_file, "CSV_ENABLED", "true"), True),
        log_file=PROJECT_ROOT / _get(env_file, "LOG_FILE", "logs/dashboard.log"),
        csv_file=PROJECT_ROOT / _get(env_file, "CSV_FILE", "data/records.csv"),
        preview_file=PROJECT_ROOT / _get(env_file, "PREVIEW_FILE", "output/preview.png"),
        lock_file=PROJECT_ROOT / _get(env_file, "LOCK_FILE", "dashboard.lock"),
        dashboard_api_url=_get(env_file, "DASHBOARD_API_URL", ""),
        eink_api_token=_get(env_file, "EINK_API_TOKEN", ""),
    )


def validate_for_live_weather(settings: Settings) -> None:
    missing = [
        key for key, value in {
            "OPENWEATHER_API_KEY": settings.api_key,
            "OPENWEATHER_LATITUDE": settings.latitude,
            "OPENWEATHER_LONGITUDE": settings.longitude,
        }.items() if not value
    ]
    if missing:
        raise ValueError(f"Missing required weather config: {', '.join(missing)}")
