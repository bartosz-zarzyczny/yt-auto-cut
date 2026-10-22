"""Logo w prawym górnym rogu filmu (maks. 100x100 px, z zachowaniem proporcji)."""
from pathlib import Path
from typing import Callable, Optional

from moviepy.editor import ImageClip

LOGO_MAX_SIZE = 200
LOGO_MARGIN = 20
LOGO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")


def resolve_logo_path(logo_path) -> Optional[Path]:
    """Zwraca ścieżkę do poprawnego pliku logo albo None, gdy logo nie jest wybrane."""
    text = str(logo_path or "").strip()
    if not text or text == ".":
        return None
    path = Path(text)
    if not path.is_file() or path.suffix.lower() not in LOGO_EXTENSIONS:
        return None
    return path


def _fit_size(width: int, height: int) -> tuple:
    """Zmniejsza wymiary do maks. 100x100 bez zmiany proporcji (nie powiększa małych logo)."""
    scale = min(LOGO_MAX_SIZE / width, LOGO_MAX_SIZE / height, 1.0)
    return max(1, round(width * scale)), max(1, round(height * scale))


def create_logo_clip(
    logo_path,
    duration: float,
    video_width: int,
    log: Optional[Callable[[str], None]] = None,
):
    """Tworzy klip z logo w prawym górnym rogu lub zwraca None, gdy logo nie wybrano/nie da się wczytać."""
    path = resolve_logo_path(logo_path)
    if path is None:
        return None
    try:
        from PIL import Image

        with Image.open(path) as image:
            image = image.convert("RGBA")
            new_size = _fit_size(*image.size)
            image = image.resize(new_size, Image.LANCZOS)
            import numpy as np

            frame = np.array(image)
    except Exception as error:
        if log:
            log(f"Nie udało się wczytać logo ({path.name}): {error}")
        return None

    clip = ImageClip(frame, ismask=False, transparent=True).set_duration(duration)
    x_position = max(0, video_width - new_size[0] - LOGO_MARGIN)
    return clip.set_position((x_position, LOGO_MARGIN))
