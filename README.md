# raspi-eink-kitchen-dashboard

A Raspberry Pi dashboard for a Waveshare 7.5" V2 e-ink display. Shows current weather, 3-day forecast, family calendar, grocery list, and a daily fact. A local web interface lets you control update schedules, force refreshes, and set timed reminders from your phone.

```
┌──────────────────┬──────────────────────────┐
│  Mon Jun 9       │  CALENDAR                │
│  [icon]  Sunny   │  • Today 6pm  Soccer     │
│                  │  • Tomorrow   Dentist     │
│       72°        ├──────────────────────────┤
│  Feels 70° Rain 0│  GROCERY                 │
│  High 81° Low 64°│  □ milk   □ eggs         │
│  Wind 8 MPH      │  □ bread  □ dog food     │
├──────────────────┼──────────────────────────┤
│ [Today][Tom][Wed]│  RANDOM FACT             │
│                  │  Emus can't walk         │
│                  │  backwards.              │
└──────────────────┴──────────────────────────┘
                              UPDATED 10:45 AM
```

## Hardware

- Raspberry Pi Zero 2W (or any Pi with SPI)
- Waveshare 7.5" V2 e-paper HAT (800×480)

## Setup

### 1. Enable SPI on the Pi

```bash
sudo raspi-config  # Interface Options → SPI → Enable
```

### 2. Install dependencies

```bash
pip3 install -r requirements.txt --break-system-packages
```

### 3. Configure

```bash
cp .env.example .env
nano .env
```

| Variable | Required | Description |
|---|---|---|
| `OPENWEATHER_API_KEY` | Yes | Free API key from openweathermap.org |
| `OPENWEATHER_LATITUDE` | Yes | Decimal latitude |
| `OPENWEATHER_LONGITUDE` | Yes | Decimal longitude |
| `OPENWEATHER_UNITS` | No | `imperial` (default), `metric`, or `standard` |
| `DASHBOARD_LOCATION` | No | Display name for location (default: `Home`) |
| `TRASH_DAYS` | No | Weekday numbers to show trash reminder, e.g. `0,3` (0=Mon) |
| `DASHBOARD_API_URL` | No | Endpoint returning calendar/grocery/facts JSON |
| `EINK_API_TOKEN` | No | Auth token sent as `x-eink-token` header |
| `CSV_ENABLED` | No | Log weather readings to CSV (default: `true`) |

## Running

**Web server — recommended.** Manages all scheduling and exposes the control UI:

```bash
python3 server.py
```

Open `http://<pi-ip>:5000` on any device on your network.

**One-shot update** (useful for testing or cron):

```bash
python3 main.py
```

**Preview without hardware** (renders a PNG instead of touching the display):

```bash
python3 main.py --preview --sample   # uses built-in sample data
python3 main.py --preview            # uses live weather API
```

## Run as a service (auto-start on boot)

```bash
sudo cp raspi-eink-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now raspi-eink-dashboard
```

On start the service does an immediate full refresh, then maintains two independent schedules:

- **Weather** — fetches current conditions and 3-day forecast every 15 minutes (configurable)
- **Family data** — fetches calendar, grocery, and facts every 60 minutes (configurable)

## Web interface

| Section | What you can do |
|---|---|
| Data Status | See last fetch time per component; force-refresh weather, family data, or everything |
| Update Schedule | Change weather and family data intervals in minutes |
| Manual Reminder | Set a message that replaces the fact section for 8 / 12 / 24 / 48 hours |

## Dashboard API

The optional `DASHBOARD_API_URL` should return JSON in this shape:

```json
{
  "calendar":   [{ "summary": "Soccer practice", "date": "2026-06-09", "time": "6:00pm" }],
  "grocery":    [{ "title": "milk", "quantity": "1" }],
  "onThisDay":  { "title": "On this day", "text": "..." },
  "randomFact": { "title": "Random fact",  "text": "..." }
}
```

If the URL is not set, calendar and grocery show empty-state messages and the fact section is omitted.

## Project layout

```
main.py                       # One-shot CLI entry point
server.py                     # Flask + APScheduler web server
dashboard/
  config.py                   # Settings loaded from .env
  weather.py                  # OpenWeatherMap One Call API
  dashboard_data.py           # Family dashboard API client
  render.py                   # PIL image renderer (800x480)
  display.py                  # Waveshare e-paper hardware driver
  cache.py                    # Thread-safe JSON cache (weather + family + reminder)
  storage.py                  # Optional CSV weather log
  lock.py                     # Single-instance file lock (used by main.py)
templates/index.html          # Web control UI
assets/                       # Font and weather icons
scripts/                      # run_once.sh, run_preview.sh helpers
raspi-eink-dashboard.service  # systemd unit file
```
