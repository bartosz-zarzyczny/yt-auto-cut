import os
import platform
import shutil
import subprocess
import sys

from moviepy.config import get_setting

from sprawdzanie_systemu import kodek_dziala, kodeki_sprzetowe, OPISY_KODEKOW, preset_dla_kodeku  # noqa: F401

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
    return kodek_dziala(get_setting("FFMPEG_BINARY"), kodek)


def wybierz_kodek():
    """Pierwszy działający kodek: NVENC (NVIDIA), AMF (AMD), QSV (Intel), VideoToolbox (macOS), libx264 (zawsze)."""
    for kodek in kodeki_sprzetowe():
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


def sprawdz_srodowisko(sciezka_magick, log_callback=None):
    """Wypisuje kolorowe komunikaty. Zwraca (czy_mozna_kontynuowac, kodek)."""
    ok = True

    def informuj(tekst, kolor=None):
        print(_kolor(tekst, kolor) if kolor else tekst)
        if log_callback:
            log_callback(tekst)

    if not sciezka_magick:
        ok = False
        informuj("BŁĄD: Nie znaleziono programu ImageMagick (potrzebny do napisów).", CZERWONY)
        informuj("  Co zrobić: " + instrukcja_imagemagick(), CZERWONY)
        informuj("  Potem uruchom skrypt ponownie.", CZERWONY)

    kodek = wybierz_kodek()
    if kodek == "libx264" and not _kodek_dziala("libx264"):
        ok = False
        informuj("BŁĄD: FFmpeg nie ma działającego kodeka wideo (libx264).", CZERWONY)
        informuj("  Co zrobić: " + instrukcja_ffmpeg(), CZERWONY)
    elif kodek == "libx264":
        informuj("UWAGA: Brak działającego kodeka sprzętowego (NVIDIA NVENC, AMD AMF, Intel QSV, "
                 "Apple VideoToolbox) - użyję libx264 (procesor). Renderowanie będzie wolniejsze, ale działa.",
                 ZOLTY)
        informuj("  Szybciej: aktualne sterowniki karty graficznej i FFmpeg z obsługą jej kodeka "
                 "(pełna wersja ze strony gyan.dev).", ZOLTY)
    else:
        informuj(f"Kodek wideo: {kodek} ({OPISY_KODEKOW.get(kodek, kodek)})", ZIELONY)

    return ok, kodek
