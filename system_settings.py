import os
import platform
import shutil
import subprocess
import sys

from moviepy.config import get_setting

from system_check import codec_works, hardware_codecs, CODEC_DESCRIPTIONS, preset_for_codec  # noqa: F401
from app_settings import find_imagemagick as _find_imagemagick_from_settings

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Windows: nazwa fontu znana ImageMagick. Pozostałe systemy: pliki czcionek zbliżonych do Arial Bold.
FONT_WINDOWS = "Arial-Bold"
FALLBACK_FONTS = [
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Linux (Liberation Sans ma metryki zgodne z Arial)
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    # Czcionka dołączona do projektu - działa zawsze
    os.path.join(PROJECT_DIR, "Fonts", "Chakra_Petch,Oxanium", "Chakra_Petch", "ChakraPetch-Bold.ttf"),
    os.path.join(PROJECT_DIR, "Fonts", "Oxanium", "static", "Oxanium-Bold.ttf"),
]


def choose_font():
    if platform.system() == "Windows":
        return FONT_WINDOWS
    for path in FALLBACK_FONTS:
        if os.path.isfile(path):
            return path
    return FONT_WINDOWS


def find_imagemagick(default_windows=None):
    """Ścieżka z settings.json lub z PATH; w ostateczności wartość domyślna przekazana w argumencie."""
    path = _find_imagemagick_from_settings()
    if path:
        return path
    if default_windows and os.path.isfile(default_windows):
        return default_windows
    return None


def _codec_is_usable(codec):
    return codec_works(get_setting("FFMPEG_BINARY"), codec)


def choose_codec():
    """Pierwszy działający kodek: NVENC (NVIDIA), AMF (AMD), QSV (Intel), VideoToolbox (macOS), libx264 (zawsze)."""
    for codec in hardware_codecs():
        if _codec_is_usable(codec):
            return codec
    return "libx264"


# --- Komunikaty w kolorach (ANSI) ---
if platform.system() == "Windows":
    os.system("")  # włącza obsługę kodów ANSI w konsoli Windows

RED, YELLOW, GREEN, RESET = "\033[91m", "\033[93m", "\033[92m", "\033[0m"


def _color(text, color):
    return f"{color}{text}{RESET}" if sys.stdout.isatty() else text


def imagemagick_instructions():
    system = platform.system()
    if system == "Darwin":
        step = "Zainstaluj: brew install imagemagick"
    elif system == "Windows":
        step = ("Pobierz z https://imagemagick.org/script/download.php#windows i przy instalacji zaznacz\n"
                "     'Install legacy utilities (e.g. convert)' oraz dodanie do PATH.")
    else:
        step = "Zainstaluj: sudo apt install imagemagick  (lub odpowiednik dla Twojej dystrybucji)"
    return step


def ffmpeg_instructions():
    system = platform.system()
    if system == "Darwin":
        return "Zainstaluj FFmpeg z libx264: brew install ffmpeg"
    if system == "Windows":
        return "Pobierz pełną wersję FFmpeg z https://www.gyan.dev/ffmpeg/builds/ i dodaj folder bin do PATH."
    return "Zainstaluj FFmpeg z libx264: sudo apt install ffmpeg"


def check_environment(magick_path, log_callback=None):
    """Wypisuje kolorowe komunikaty. Zwraca (czy_mozna_kontynuowac, kodek)."""
    ok = True

    def inform(text, color=None):
        print(_color(text, color) if color else text)
        if log_callback:
            log_callback(text)

    if not magick_path:
        ok = False
        inform("BŁĄD: Nie znaleziono programu ImageMagick (potrzebny do napisów).", RED)
        inform("  Co zrobić: " + imagemagick_instructions(), RED)
        inform("  Potem uruchom skrypt ponownie.", RED)

    codec = choose_codec()
    if codec == "libx264" and not _codec_is_usable("libx264"):
        ok = False
        inform("BŁĄD: FFmpeg nie ma działającego kodeka wideo (libx264).", RED)
        inform("  Co zrobić: " + ffmpeg_instructions(), RED)
    elif codec == "libx264":
        inform("UWAGA: Brak działającego kodeka sprzętowego (NVIDIA NVENC, AMD AMF, Intel QSV, "
               "Apple VideoToolbox) - użyję libx264 (procesor). Renderowanie będzie wolniejsze, ale działa.",
               YELLOW)
        inform("  Szybciej: aktualne sterowniki karty graficznej i FFmpeg z obsługą jej kodeka "
               "(pełna wersja ze strony gyan.dev).", YELLOW)
    else:
        inform(f"Kodek wideo: {codec} ({CODEC_DESCRIPTIONS.get(codec, codec)})", GREEN)

    return ok, codec
