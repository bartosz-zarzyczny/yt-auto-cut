"""Napisy rysowane przez Pillow (bez ImageMagick) — działa tak samo na Windows i macOS."""
import math
from functools import lru_cache
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

LINE_SPACING = 0.15  # odstęp między liniami jako ułamek rozmiaru czcionki


@lru_cache(maxsize=32)
def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(font_path, size)
    except OSError as error:
        raise OSError(f"Nie można wczytać czcionki {font_path}: {error}") from error


def _measure(draw: ImageDraw.ImageDraw, text: str, font, stroke_width: int, spacing: int, align: str):
    return draw.multiline_textbbox(
        (0, 0), text, font=font, stroke_width=stroke_width, spacing=spacing, align=align
    )


def wrap_text(text: str, font, max_width: int, stroke_width: int = 0) -> str:
    """Łamie tekst na linie mieszczące się w max_width (jak tryb „caption” ImageMagick)."""
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))

    def width(line: str) -> int:
        left, _, right, _ = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        return right - left

    lines: List[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and width(candidate) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return "\n".join(lines)


def render_text(
    text: str,
    font_path: str,
    font_size: int,
    color: str = "white",
    stroke_color: Optional[str] = None,
    stroke_width: float = 0,
    max_width: Optional[int] = None,
    align: str = "center",
) -> np.ndarray:
    """Zwraca obraz RGBA (numpy) z tekstem i obrysem, przycięty do treści.

    max_width łamie linie i ustala szerokość obrazu na dokładnie max_width (wyśrodkowany tekst)."""
    font = load_font(str(font_path), int(font_size))
    stroke = int(round(stroke_width)) if stroke_color else 0
    if max_width:
        text = wrap_text(text, font, max_width, stroke)
    spacing = int(round(font_size * LINE_SPACING))
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    left, top, right, bottom = _measure(draw, text, font, stroke, spacing, align)
    # Nowsze Pillow zwracają współrzędne jako float — zaokrąglamy na zewnątrz, żeby nie uciąć obrysu.
    left, top, right, bottom = math.floor(left), math.floor(top), math.ceil(right), math.ceil(bottom)
    text_width = right - left
    width = max(max_width or 0, text_width, 1)
    height = max(bottom - top, 1)

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = (width - text_width) // 2 - left
    ImageDraw.Draw(image).multiline_text(
        (x, -top),
        text,
        font=font,
        fill=color,
        stroke_width=stroke,
        stroke_fill=stroke_color,
        spacing=spacing,
        align=align,
    )
    return np.array(image)


def text_clip(text: str, duration: float, **style):
    """Klip MoviePy z przezroczystym tłem (kanał alfa staje się maską)."""
    from moviepy.editor import ImageClip

    return ImageClip(render_text(text, **style), transparent=True).set_duration(duration)
