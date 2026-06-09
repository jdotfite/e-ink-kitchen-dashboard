from __future__ import annotations

import logging
import sys
from pathlib import Path
from PIL import Image


def update_display(image: Image.Image) -> None:
    """Update Waveshare 7.5 V2 display. Hardware is imported lazily for testability."""
    driver_path = Path(__file__).resolve().parent / "drivers"
    sys.path.insert(0, str(driver_path))
    from waveshare_epd import epd7in5_V2  # type: ignore

    epd = epd7in5_V2.EPD()
    initialized = False
    try:
        if epd.init() != 0:
            raise RuntimeError("Failed to initialize Waveshare e-paper display")
        initialized = True
        canvas = Image.new("1", (epd.width, epd.height), 255)
        canvas.paste(image.convert("1"), (0, 0))
        epd.display(epd.getbuffer(canvas))
        logging.info("Image displayed on e-paper successfully")
    finally:
        if initialized:
            try:
                epd.sleep()
            except Exception:
                logging.exception("Failed to put e-paper display to sleep")
            if hasattr(epd, "Dev_exit"):
                try:
                    epd.Dev_exit()
                except Exception:
                    logging.exception("Failed to clean up e-paper GPIO/SPI resources")
