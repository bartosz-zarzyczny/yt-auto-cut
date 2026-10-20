import importlib
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from typing import List

# (nazwa pakietu w pip, wymagana wersja)
BIBLIOTEKI = (
    ("moviepy", "<2.0.0"),
    ("decorator", "==4.4.2"),
    ("numpy", ""),
    ("librosa", ""),
    ("scipy", ""),
    ("Pillow", ""),
    ("PySide6", ">=6.5,<7"),
    ("google-auth", ""),
    ("google-api-python-client", ""),
    ("google-auth-oauthlib", ""),
    ("google-auth-httplib2", ""),
    ("tzdata", ""),
)

IMAGEMAGICK_WINDOWS = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

# Sprzętowe kodeki H.264 w kolejności prób. AMF ma własne nazwy presetów (speed/balanced/quality).
KODEKI_SPRZETOWE_WINDOWS_LINUX = ("h264_nvenc", "h264_amf", "h264_qsv")
KODEKI_SPRZETOWE_MACOS = ("h264_videotoolbox",)
OPISY_KODEKOW = {
    "h264_nvenc": "NVIDIA NVENC",
    "h264_amf": "AMD AMF",
    "h264_qsv": "Intel Quick Sync",
    "h264_videotoolbox": "Apple VideoToolbox",
    "libx264": "procesor (libx264)",
}
PRESETY_KODEKOW = {"h264_amf": "speed"}
PRESET_DOMYSLNY = "fast"


def kodeki_sprzetowe():
    return KODEKI_SPRZETOWE_MACOS if platform.system() == "Darwin" else KODEKI_SPRZETOWE_WINDOWS_LINUX


def preset_dla_kodeku(kodek):
    return PRESETY_KODEKOW.get(kodek, PRESET_DOMYSLNY)


def kodek_dziala(ffmpeg, kodek):
    """Próbne kodowanie z tymi samymi opcjami, których używa montaż (preset, pix_fmt)."""
    komenda = [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=0.2",
               "-c:v", kodek, "-preset", preset_dla_kodeku(kodek), "-pix_fmt", "yuv420p",
               "-f", "null", "-"]
    try:
        return subprocess.run(komenda, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@dataclass
class WynikTestu:
    nazwa: str
    ok: bool
    wersja: str
    uwaga: str = ""
    instalacja: str = ""


def _wersja_pakietu(nazwa):
    try:
        return metadata.version(nazwa)
    except metadata.PackageNotFoundError:
        return None


def _spelnia_wymaganie(wersja, wymaganie):
    if not wymaganie:
        return True
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
        return Version(wersja) in SpecifierSet(wymaganie)
    except Exception:
        return True


def _pierwsza_linia(komenda):
    try:
        wynik = subprocess.run(komenda, capture_output=True, text=True, timeout=30,
                               encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    tekst = (wynik.stdout or wynik.stderr).strip()
    return tekst.splitlines()[0] if tekst else ""


IMPORTY = {
    "moviepy": "moviepy.editor",
    "Pillow": "PIL",
    "google-auth": "google.auth",
    "google-api-python-client": "googleapiclient",
    "google-auth-oauthlib": "google_auth_oauthlib",
    "google-auth-httplib2": "google_auth_httplib2",
}


def _blad_importu(pakiet):
    modul = IMPORTY.get(pakiet, pakiet.replace("-", "_"))
    try:
        importlib.import_module(modul)
    except Exception as blad:
        return f"{type(blad).__name__}: {blad}"
    return None


def sprawdz_biblioteki() -> List[WynikTestu]:
    wyniki = []
    for nazwa, wymaganie in BIBLIOTEKI:
        wersja = _wersja_pakietu(nazwa)
        polecenie = f'"{sys.executable}" -m pip install "{nazwa}{wymaganie}"'
        if wersja is None:
            wyniki.append(WynikTestu(nazwa, False, "brak", "Nie zainstalowano", polecenie))
        elif not _spelnia_wymaganie(wersja, wymaganie):
            wyniki.append(WynikTestu(nazwa, False, wersja, f"Wymagana wersja {wymaganie}", polecenie))
        elif (blad := _blad_importu(nazwa)) is not None:
            wyniki.append(WynikTestu(nazwa, False, wersja, f"Nie można zaimportować ({blad})",
                                     polecenie.replace("pip install", "pip install --force-reinstall")))
        else:
            wyniki.append(WynikTestu(nazwa, True, wersja, f"wymagane {wymaganie}" if wymaganie else ""))
    return wyniki


def _instrukcja_ffmpeg():
    system = platform.system()
    if system == "Darwin":
        return "Zainstaluj FFmpeg z libx264: brew install ffmpeg"
    if system == "Windows":
        return "Pobierz pełną wersję FFmpeg z https://www.gyan.dev/ffmpeg/builds/ i dodaj folder bin do PATH."
    return "Zainstaluj FFmpeg z libx264: sudo apt install ffmpeg"


def _instrukcja_imagemagick():
    system = platform.system()
    if system == "Darwin":
        return "Zainstaluj: brew install imagemagick"
    if system == "Windows":
        return ("Pobierz z https://imagemagick.org/script/download.php#windows i przy instalacji "
                "zaznacz 'Install legacy utilities (e.g. convert)' oraz dodanie do PATH.")
    return "Zainstaluj: sudo apt install imagemagick"


def _znajdz_ffmpeg():
    """FFmpeg używany przez MoviePy (jeśli dostępny), w przeciwnym razie z PATH."""
    try:
        from moviepy.config import get_setting
        return get_setting("FFMPEG_BINARY")
    except Exception:
        return shutil.which("ffmpeg")


def sprawdz_oprogramowanie() -> List[WynikTestu]:
    wyniki = []
    ffmpeg = _znajdz_ffmpeg()
    wersja = _pierwsza_linia([ffmpeg, "-version"]) if ffmpeg else None
    if wersja is None:
        wyniki.append(WynikTestu("FFmpeg", False, "brak", "Nie znaleziono lub nie uruchamia się",
                                 _instrukcja_ffmpeg()))
        wyniki.append(WynikTestu("Kodek libx264", False, "brak", "Wymaga FFmpeg", _instrukcja_ffmpeg()))
    else:
        numer = wersja.replace("ffmpeg version ", "").split()[0] if wersja else "nieznana"
        wyniki.append(WynikTestu("FFmpeg", True, numer, ffmpeg))
        if kodek_dziala(ffmpeg, "libx264"):
            wyniki.append(WynikTestu("Kodek libx264", True, "działa"))
        else:
            wyniki.append(WynikTestu("Kodek libx264", False, "brak", "FFmpeg bez libx264",
                                     _instrukcja_ffmpeg()))
        sprawdzone = [k for k in kodeki_sprzetowe()]
        dzialajace = [k for k in sprawdzone if kodek_dziala(ffmpeg, k)]
        if dzialajace:
            wyniki.append(WynikTestu(
                "Kodek sprzętowy (opcjonalny)", True, dzialajace[0],
                f"{OPISY_KODEKOW.get(dzialajace[0], '')}; użyty zostanie pierwszy działający"))
        else:
            wyniki.append(WynikTestu(
                "Kodek sprzętowy (opcjonalny)", True, "niedostępny",
                f"Sprawdzono: {', '.join(sprawdzone)}. Montaż użyje libx264 (wolniej, ale działa wszędzie)"))

    sciezka = shutil.which("magick") or shutil.which("convert")
    if not sciezka and platform.system() == "Windows" and os.path.isfile(IMAGEMAGICK_WINDOWS):
        sciezka = IMAGEMAGICK_WINDOWS
    if not sciezka:
        wyniki.append(WynikTestu("ImageMagick", False, "brak", "Potrzebny do napisów",
                                 _instrukcja_imagemagick()))
    else:
        wersja = " ".join((_pierwsza_linia([sciezka, "-version"]) or "nieznana").split()[:3])
        wyniki.append(WynikTestu("ImageMagick", True, wersja, sciezka))
    return wyniki


def uruchom_test_systemu() -> List[WynikTestu]:
    wyniki = [WynikTestu("Python", sys.version_info >= (3, 8), platform.python_version(),
                         f"{platform.system()} {platform.release()}",
                         "Zainstaluj Python 3.8 lub nowszy z python.org")]
    wyniki.extend(sprawdz_biblioteki())
    wyniki.extend(sprawdz_oprogramowanie())
    return wyniki


def formatuj_tekst(wyniki: List[WynikTestu]) -> str:
    linie = ["TEST SYSTEMU", ""]
    for w in wyniki:
        linie.append(f"[{'OK' if w.ok else 'BRAK'}] {w.nazwa}: {w.wersja}" + (f"  ({w.uwaga})" if w.uwaga else ""))
    braki = [w for w in wyniki if not w.ok]
    linie.append("")
    if braki:
        linie.append("DO DOINSTALOWANIA / NAPRAWY:")
        linie.extend(f"  - {w.nazwa}: {w.instalacja}" for w in braki)
        linie.append("")
        linie.append("Po instalacji uruchom aplikację ponownie.")
    else:
        linie.append("Wszystko gotowe do pracy.")
    return "\n".join(linie)


def pokaz_raport_bez_qt():
    """Awaryjny raport, gdy nie da się uruchomić okna Qt (np. brak PySide6)."""
    tekst = formatuj_tekst(uruchom_test_systemu())
    try:
        import tkinter
        from tkinter import scrolledtext
        okno = tkinter.Tk()
        okno.title("IPSC Video Automato — brakujące składniki")
        okno.geometry("900x560")
        pole = scrolledtext.ScrolledText(okno, font=("Consolas", 10), wrap="word")
        pole.insert("1.0", "Nie można uruchomić interfejsu aplikacji.\n\n" + tekst)
        pole.configure(state="disabled")
        pole.pack(fill="both", expand=True)
        okno.mainloop()
    except Exception:
        print(tekst)


def formatuj_html(wyniki: List[WynikTestu]) -> str:
    def esc(tekst):
        return tekst.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    wiersze = []
    for w in wyniki:
        znak = "<span style='color:#43e0c1'>✔</span>" if w.ok else "<span style='color:#ff7b7b'>✘</span>"
        wiersze.append(
            f"<tr><td>{znak}</td><td><b>{esc(w.nazwa)}</b></td><td>{esc(w.wersja)}</td>"
            f"<td style='color:#8998ac'>{esc(w.uwaga)}</td></tr>"
        )
    braki = [w for w in wyniki if not w.ok]
    html = ["<h2>Test systemu</h2><table cellspacing='0' cellpadding='4'>", *wiersze, "</table>"]
    if braki:
        html.append("<h3 style='color:#ff7b7b'>Do doinstalowania / naprawy</h3><ul>")
        for w in braki:
            html.append(f"<li><b>{esc(w.nazwa)}</b>: <code>{esc(w.instalacja)}</code></li>")
        html.append("</ul>")
    else:
        html.append("<h3 style='color:#43e0c1'>Wszystko gotowe do pracy.</h3>")
    return "".join(html)
