import os
import platform
import shutil
import subprocess
import sys

from moviepy.config import get_setting

KATALOG_PROJEKTU = os.path.dirname(os.path.abspath(__file__))

# Windows: nazwa fontu znana ImageMagick. Pozostałe systemy: pliki czcionek zbliżonych do Arial Bold.
CZCIONKA_WINDOWS = "Arial-Bold"
CZCIONKI_ZAPASOWE = [
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
    os.path.join(KATALOG_PROJEKTU, "Fonts", "Chakra_Petch,Oxanium", "Chakra_Petch", "ChakraPetch-Bold.ttf"),
    os.path.join(KATALOG_PROJEKTU, "Fonts", "Oxanium", "static", "Oxanium-Bold.ttf"),
]


def wybierz_czcionke():
    if platform.system() == "Windows":
        return CZCIONKA_WINDOWS
    for sciezka in CZCIONKI_ZAPASOWE:
        if os.path.isfile(sciezka):
            return sciezka
    return CZCIONKA_WINDOWS


def znajdz_imagemagick(domyslna_windows=None):
    """Zwraca ścieżkę do ImageMagick z PATH, a w ostateczności wartość domyślną (Windows)."""
    for nazwa in ("magick", "convert"):
        sciezka = shutil.which(nazwa)
        if sciezka:
            return sciezka
    if domyslna_windows and os.path.isfile(domyslna_windows):
        return domyslna_windows
    return None


def _kodek_dziala(kodek):
    # Próbne kodowanie z tymi samymi opcjami, których używa MoviePy (w tym -preset)
    cmd = [get_setting("FFMPEG_BINARY"), "-v", "error", "-f", "lavfi",
           "-i", "color=c=black:s=256x256:d=0.2", "-c:v", kodek,
           "-preset", "fast", "-pix_fmt", "yuv420p", "-f", "null", "-"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def wybierz_kodek():
    """Pierwszy działający kodek: NVENC (NVIDIA), VideoToolbox (macOS), libx264 (zawsze)."""
    kandydaci = ["h264_nvenc"]
    if platform.system() == "Darwin":
        kandydaci.append("h264_videotoolbox")
    for kodek in kandydaci:
        if _kodek_dziala(kodek):
            return kodek
    return "libx264"


# --- Komunikaty w kolorach (ANSI) ---
if platform.system() == "Windows":
    os.system("")  # włącza obsługę kodów ANSI w konsoli Windows

CZERWONY, ZOLTY, ZIELONY, RESET = "\033[91m", "\033[93m", "\033[92m", "\033[0m"


def _kolor(tekst, kolor):
    return f"{kolor}{tekst}{RESET}" if sys.stdout.isatty() else tekst


def instrukcja_imagemagick():
    system = platform.system()
    if system == "Darwin":
        krok = "Zainstaluj: brew install imagemagick"
    elif system == "Windows":
        krok = ("Pobierz z https://imagemagick.org/script/download.php#windows i przy instalacji zaznacz\n"
                "     'Install legacy utilities (e.g. convert)' oraz dodanie do PATH.")
    else:
        krok = "Zainstaluj: sudo apt install imagemagick  (lub odpowiednik dla Twojej dystrybucji)"
    return krok


def instrukcja_ffmpeg():
    system = platform.system()
    if system == "Darwin":
        return "Zainstaluj FFmpeg z libx264: brew install ffmpeg"
    if system == "Windows":
        return "Pobierz pełną wersję FFmpeg z https://www.gyan.dev/ffmpeg/builds/ i dodaj folder bin do PATH."
    return "Zainstaluj FFmpeg z libx264: sudo apt install ffmpeg"


def sprawdz_srodowisko(sciezka_magick):
    """Wypisuje kolorowe komunikaty. Zwraca (czy_mozna_kontynuowac, kodek)."""
    ok = True

    if not sciezka_magick:
        ok = False
        print(_kolor("BŁĄD: Nie znaleziono programu ImageMagick (potrzebny do napisów).", CZERWONY))
        print(_kolor("  Co zrobić: " + instrukcja_imagemagick(), CZERWONY))
        print(_kolor("  Potem uruchom skrypt ponownie.", CZERWONY))

    kodek = wybierz_kodek()
    if kodek == "libx264" and not _kodek_dziala("libx264"):
        ok = False
        print(_kolor("BŁĄD: FFmpeg nie ma działającego kodeka wideo (libx264).", CZERWONY))
        print(_kolor("  Co zrobić: " + instrukcja_ffmpeg(), CZERWONY))
    elif kodek == "libx264":
        print(_kolor("UWAGA: Brak sprzętowego kodeka (NVENC/VideoToolbox) - użyję libx264. "
                     "Renderowanie będzie wolniejsze.", ZOLTY))
        print(_kolor("  Szybciej: karta NVIDIA i aktualne sterowniki lub FFmpeg z obsługą h264_nvenc.", ZOLTY))
    else:
        print(_kolor(f"Kodek wideo: {kodek}", ZIELONY))

    return ok, kodek
