"""Ustawienia projektu zapisywane w settings.json (bez ciężkich importów)."""
import json
import os
import platform
import shutil
from pathlib import Path

SETTINGS_FILE = Path(__file__).resolve().parent / "settings.json"
KEY_IMAGEMAGICK = "imagemagick_path"
KEY_BUFFER_API = "BUFFER_API"
IMAGEMAGICK_DEFAULT_WINDOWS = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"


def _default_settings():
    default = IMAGEMAGICK_DEFAULT_WINDOWS if platform.system() == "Windows" else ""
    return {KEY_IMAGEMAGICK: default}


def load_settings(file_path=SETTINGS_FILE):
    """Wczytuje settings.json; brakujący lub uszkodzony plik daje ustawienia domyślne."""
    settings = _default_settings()
    try:
        data = json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return settings
    if isinstance(data, dict):
        settings.update(data)
    return settings


def save_settings(settings, file_path=SETTINGS_FILE):
    file_path = Path(file_path)
    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(file_path)


def ensure_settings_file(file_path=SETTINGS_FILE):
    """Tworzy settings.json z wartościami domyślnymi (przeniesionymi z kodu), jeśli go nie ma."""
    if not Path(file_path).exists():
        try:
            save_settings(_default_settings(), file_path)
        except OSError:
            pass


def saved_imagemagick_path(file_path=SETTINGS_FILE):
    return str(load_settings(file_path).get(KEY_IMAGEMAGICK) or "").strip()


def saved_buffer_api_key(file_path=SETTINGS_FILE):
    return str(load_settings(file_path).get(KEY_BUFFER_API) or "").strip()


def save_imagemagick_path(path, file_path=SETTINGS_FILE):
    settings = load_settings(file_path)
    settings[KEY_IMAGEMAGICK] = str(path).strip()
    save_settings(settings, file_path)


def find_imagemagick(file_path=SETTINGS_FILE):
    """Ścieżka z settings.json (jeśli plik istnieje), w przeciwnym razie magick/convert z PATH."""
    saved = saved_imagemagick_path(file_path)
    if saved and os.path.isfile(saved):
        return saved
    for name in ("magick", "convert"):
        path = shutil.which(name)
        if path:
            return path
    return None
