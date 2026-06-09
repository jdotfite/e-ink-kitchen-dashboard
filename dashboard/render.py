from __future__ import annotations

from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

from .config import PROJECT_ROOT, Settings
from .dashboard_data import FamilyDashboard, FactBlock
from .weather import ForecastDay, WeatherReport

WIDTH = 800
HEIGHT = 480
ASSET_DIR = PROJECT_ROOT / "assets"
FONT_PATH = ASSET_DIR / "font" / "Font.ttc"
ICON_DIR = ASSET_DIR / "icons"
BLACK = 0
WHITE = 255


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, min_size: int = 14):
    text = str(text or "")
    size = start_size
    while size > min_size:
        font = _font(size)
        if _text_size(draw, text, font)[0] <= max_width:
            return font, text
        size -= 2
    font = _font(min_size)
    ellipsis = "..."
    while text and _text_size(draw, text + ellipsis, font)[0] > max_width:
        text = text[:-1]
    return font, (text + ellipsis) if text else ellipsis


def _draw_fitted(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, max_width: int, size: int, fill=BLACK, min_size: int = 14):
    font, fitted = _fit_text(draw, text, max_width, size, min_size)
    draw.text(xy, fitted, font=font, fill=fill)
    return fitted


def _ellipsize(draw: ImageDraw.ImageDraw, text: str, max_width: int, font) -> str:
    text = str(text or "")
    if _text_size(draw, text, font)[0] <= max_width:
        return text
    ellipsis = "..."
    while text and _text_size(draw, text + ellipsis, font)[0] > max_width:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis


def _draw_fixed_bold(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, max_width: int, size: int, fill=BLACK):
    font = _font(size)
    fitted = _ellipsize(draw, text, max_width, font)
    draw.text(xy, fitted, font=font, fill=fill)
    draw.text((xy[0] + 1, xy[1]), fitted, font=font, fill=fill)


def _draw_centered_bold(draw: ImageDraw.ImageDraw, center_x: int, y: int, text: str, max_width: int, size: int, fill=BLACK, min_size: int = 12):
    font, fitted = _fit_text(draw, text, max_width, size, min_size)
    width, _ = _text_size(draw, fitted, font)
    x = center_x - width // 2
    draw.text((x, y), fitted, font=font, fill=fill)
    draw.text((x + 1, y), fitted, font=font, fill=fill)


def _draw_centered_wrapped_bold(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, text: str, max_width: int, size: int, max_lines: int = 2, fill=BLACK, line_gap: int = 2):
    font = _font(size)
    lines = _wrap_text(draw, text, max_width, font)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and _text_size(draw, lines[-1] + "...", font)[0] > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = f"{lines[-1]}..."
    _, line_h = _text_size(draw, "Ag", font)
    block_h = len(lines) * line_h + max(0, len(lines) - 1) * line_gap
    y = center_y - block_h // 2
    for line in lines:
        width, _ = _text_size(draw, line, font)
        x = center_x - width // 2
        draw.text((x, y), line, font=font, fill=fill)
        draw.text((x + 1, y), line, font=font, fill=fill)
        y += line_h + line_gap


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, font) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_wrapped_bold(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, max_width: int, max_lines: int, size: int, fill=BLACK, line_gap: int = 4):
    font = _font(size)
    lines = _wrap_text(draw, text, max_width, font)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and _text_size(draw, lines[-1] + "...", font)[0] > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = f"{lines[-1]}..."
    _, line_h = _text_size(draw, "Ag", font)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        draw.text((x + 1, y), line, font=font, fill=fill)
        y += line_h + line_gap
    return y


def _draw_section_title(draw: ImageDraw.ImageDraw, xy: tuple[int, int], title: str, max_width: int):
    x, y = xy
    font, fitted = _fit_text(draw, title.upper(), max_width, 26, 20)
    draw.text((x, y), fitted, font=font, fill=BLACK)
    draw.text((x + 1, y), fitted, font=font, fill=BLACK)
    draw.line((x, y + 33, x + max_width, y + 33), fill=BLACK, width=2)


def _paste_icon(image: Image.Image, icon_code: str, xy: tuple[int, int], size: int) -> float:
    icon_path = ICON_DIR / f"{icon_code}.png"
    if not icon_path.exists():
        return xy[1] + size / 2
    icon = Image.open(icon_path).convert("L").resize((size, size))
    image.paste(icon, xy)
    # Align text to the visual center of the non-white icon pixels, not the file
    # box center; weather icon artwork has uneven top/bottom whitespace.
    mask = icon.point(lambda pixel: 255 if pixel < 245 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return xy[1] + size / 2
    return xy[1] + (bbox[1] + bbox[3]) / 2


def _trash_today(settings: Settings, now: datetime) -> bool:
    return now.weekday() in set(settings.trash_days)


def _day_label(date_text: str, now: datetime) -> str:
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    if date_text == today:
        return "Today"
    if date_text == tomorrow:
        return "Tomorrow"
    try:
        return datetime.fromisoformat(date_text).strftime("%a")
    except ValueError:
        return "Soon"


def _fallback_forecast(report: WeatherReport) -> tuple[ForecastDay, ...]:
    return (
        ForecastDay("Wed", report.icon_code, report.temp_max, report.temp_min, report.precip_percent),
        ForecastDay("Thu", report.icon_code, report.temp_max - 2, report.temp_min - 1, report.precip_percent),
        ForecastDay("Fri", report.icon_code, report.temp_max - 4, report.temp_min - 2, report.precip_percent),
    )


def _draw_weather(draw: ImageDraw.ImageDraw, image: Image.Image, report: WeatherReport, settings: Settings, now: datetime):
    left_w = 320
    date_text = now.strftime("%b  %d   %A")
    font, fitted = _fit_text(draw, date_text, left_w - 36, 27, 20)
    tw, _ = _text_size(draw, fitted, font)
    date_x = (left_w - tw) // 2
    draw.text((date_x, 18), fitted, font=font, fill=BLACK)
    draw.text((date_x + 1, 18), fitted, font=font, fill=BLACK)

    icon_y = 56
    icon_size = 112
    icon_center_y = _paste_icon(image, report.icon_code, (28, icon_y), icon_size)
    _draw_centered_wrapped_bold(draw, 222, int(icon_center_y), report.description.title(), 166, 29, max_lines=2)

    temp = f"{report.temp_current:.0f}°"
    temp_font = _font(91)
    tw, _ = _text_size(draw, temp, temp_font)
    draw.text(((left_w - tw) // 2, 151), temp, font=temp_font, fill=BLACK)

    feels_text = f"Feels {report.feels_like:.0f}{settings.temp_unit}  Rain {report.precip_percent:.0f}%"
    _draw_centered_bold(draw, left_w // 2, 255, feels_text, left_w - 40, 24, min_size=19)

    stat_y = 290
    _draw_centered_bold(draw, 64, stat_y, f"High {report.temp_max:.0f}°", 88, 18, min_size=14)
    _draw_centered_bold(draw, 160, stat_y, f"Low {report.temp_min:.0f}°", 88, 18, min_size=14)
    _draw_centered_bold(draw, 256, stat_y, f"Wind {report.wind:.0f} {settings.wind_unit}", 104, 18, min_size=14)
    draw.line((18, 327, 302, 327), fill=BLACK, width=2)
    if _trash_today(settings, now):
        draw.rectangle((28, 328, 292, 354), fill=BLACK)
        _draw_fitted(draw, (38, 331), "TAKE OUT TRASH", 240, 17, fill=WHITE, min_size=13)

    forecast = report.forecast or _fallback_forecast(report)
    col_lefts = [10, 110, 210]
    col_w = 100
    for x, day in zip(col_lefts, forecast[:3]):
        center_x = x + col_w // 2
        _paste_icon(image, day.icon_code, (center_x - 27, 336), 54)
        _draw_centered_bold(draw, center_x, 388, day.label, col_w - 12, 18, min_size=14)
        _draw_centered_bold(draw, center_x, 412, f"{day.temp_min:.0f}-{day.temp_max:.0f}°", col_w - 8, 21, min_size=16)
        _draw_centered_bold(draw, center_x, 438, f"Rain {day.precip_percent:.0f}%", col_w - 8, 18, min_size=14)


def _draw_calendar(draw: ImageDraw.ImageDraw, family: FamilyDashboard, now: datetime):
    x, y, w = 342, 16, 438
    _draw_section_title(draw, (x, y), "Calendar", w)
    y += 43
    if not family.calendar:
        draw.text((x, y), "No upcoming family events", font=_font(21), fill=BLACK)
        return 108
    for event in family.calendar[:4]:
        day = _day_label(event.date, now)
        prefix = f"{day} {event.time}".strip()
        _draw_fixed_bold(draw, (x, y), f"• {prefix}  {event.summary}", w, 22)
        y += 32
    return y


def _draw_grocery(draw: ImageDraw.ImageDraw, family: FamilyDashboard, start_y: int):
    x, w = 342, 438
    y = max(176, start_y + 10)
    _draw_section_title(draw, (x, y), "Grocery", w)
    y += 44
    if not family.grocery:
        draw.text((x, y), "Grocery list is empty", font=_font(23), fill=BLACK)
        return y + 34

    col_w = 205
    row_h = 31
    max_rows = 4
    shown = family.grocery[: max_rows * 2]
    for idx, item in enumerate(shown):
        col = idx // max_rows
        row = idx % max_rows
        ix = x + col * (col_w + 24)
        iy = y + row * row_h
        text = f"□ {item.quantity + ' ' if item.quantity else ''}{item.title}"
        _draw_fixed_bold(draw, (ix, iy), text, col_w, 23)
    if len(family.grocery) > len(shown):
        _draw_fitted(draw, (x + col_w + 24, y + (max_rows - 1) * row_h), f"+ {len(family.grocery) - len(shown)} more", col_w, 18, min_size=14)
    return y + max_rows * row_h


def _draw_fact(draw: ImageDraw.ImageDraw, family: FamilyDashboard, start_y: int, reminder: FactBlock | None = None):
    x, w = 342, 438
    y = max(start_y + 6, 354)
    if reminder is not None:
        fact_title = reminder.title
        fact_text = reminder.text
    else:
        fact = family.random_fact or family.on_this_day
        if not fact:
            fact_title = "Quick add"
            fact_text = "Add groceries from Discord, Alexa, or the web app."
        else:
            fact_title = fact.title
            fact_text = fact.text
    _draw_section_title(draw, (x, y), fact_title, w)
    _draw_wrapped_bold(draw, (x, y + 45), fact_text, w, 3, 23, line_gap=2)


def render_dashboard(report: WeatherReport, settings: Settings, now: datetime | None = None, family: FamilyDashboard | None = None, reminder: FactBlock | None = None) -> Image.Image:
    now = now or datetime.now()
    family = family or FamilyDashboard()
    image = Image.new("L", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), outline=BLACK, width=3)
    draw.line((320, 0, 320, HEIGHT), fill=BLACK, width=3)

    _draw_weather(draw, image, report, settings, now)
    calendar_end = _draw_calendar(draw, family, now)
    grocery_end = _draw_grocery(draw, family, calendar_end)
    _draw_fact(draw, family, grocery_end, reminder=reminder)

    updated = f"UPDATED {now.strftime('%I:%M %p').lstrip('0')}"
    updated_font = _font(15)
    text_w, _ = _text_size(draw, updated, updated_font)
    box_w = text_w + 22
    box_x = WIDTH - 1 - box_w
    box_y = HEIGHT - 29
    draw.rectangle((box_x, box_y, WIDTH - 1, HEIGHT - 1), fill=BLACK)
    draw.text((box_x + 11, box_y + 5), updated, font=updated_font, fill=WHITE)

    return image.convert("1")
