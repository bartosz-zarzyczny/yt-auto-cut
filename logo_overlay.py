"""Logo w prawym górnym rogu filmu (maks. LOGO_MAX_SIZE x LOGO_MAX_SIZE px, z zachowaniem proporcji)."""
from pathlib import Path
from typing import Callable, Optional

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
    """Zmniejsza wymiary do maks. LOGO_MAX_SIZE bez zmiany proporcji (nie powiększa małych logo)."""
    scale = min(LOGO_MAX_SIZE / width, LOGO_MAX_SIZE / height, 1.0)
    return max(1, round(width * scale)), max(1, round(height * scale))


def prepare_logo(logo_path, log: Optional[Callable[[str], None]] = None):
    """Obraz logo (PIL, RGBA) gotowy do nałożenia albo None, gdy logo nie wybrano / nie da się wczytać."""
    path = resolve_logo_path(logo_path)
    if path is None:
        return None
    try:
        from PIL import Image

        with Image.open(path) as image:
            image = image.convert("RGBA")
            return image.resize(_fit_size(*image.size), Image.LANCZOS)
    except Exception as error:
        if log:
            log(f"Nie udało się wczytać logo ({path.name}): {error}")
        return None


def logo_position(logo_width: int, video_width: int) -> tuple:
    """Lewy górny róg logo: prawy górny róg filmu z marginesem."""
    return max(0, video_width - logo_width - LOGO_MARGIN), LOGO_MARGIN
