import os
import platform
import sys
from functools import lru_cache

from moviepy.config import get_setting

from system_check import codec_works, hardware_codecs, CODEC_DESCRIPTIONS, preset_for_codec  # noqa: F401

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Plik czcionki planszy wyników (rysowanej przez Pillow): Arial Bold z systemu, a gdy go brak — podobne
# czcionki systemowe; czcionka dołączona do projektu działa zawsze.
RESULT_FONTS = [
    # Windows
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"),
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    # Linux (Liberation Sans ma metryki zgodne z Arial)
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]
BUNDLED_FONT = os.path.join(PROJECT_DIR, "Fonts", "Chakra_Petch,Oxanium", "Chakra_Petch", "ChakraPetch-Bold.ttf")


def choose_font():
    """Ścieżka do pliku czcionki planszy wyników."""
    for path in RESULT_FONTS:
        if os.path.isfile(path):
            return path
    return BUNDLED_FONT


def _codec_is_usable(codec):
    return codec_works(get_setting("FFMPEG_BINARY"), codec)


@lru_cache(maxsize=None)
def choose_codec():
    """Pierwszy działający kodek: NVENC (NVIDIA), AMF (AMD), QSV (Intel), VideoToolbox (macOS), libx264 (zawsze).

    Wynik jest zapamiętywany do końca działania programu, żeby kolejne montaże nie powtarzały próbnego kodowania."""
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


def ffmpeg_instructions():
    system = platform.system()
    if system == "Darwin":
        return "Zainstaluj FFmpeg z libx264: brew install ffmpeg"
    if system == "Windows":
        return "Pobierz pełną wersję FFmpeg z https://www.gyan.dev/ffmpeg/builds/ i dodaj folder bin do PATH."
    return "Zainstaluj FFmpeg z libx264: sudo apt install ffmpeg"


def check_environment(log_callback=None):
    """Wypisuje kolorowe komunikaty. Zwraca (czy_mozna_kontynuowac, kodek)."""
    ok = True

    def inform(text, color=None):
        print(_color(text, color) if color else text)
        if log_callback:
            log_callback(text)

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
