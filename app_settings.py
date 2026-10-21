"""Ustawienia projektu zapisywane w settings.json (bez ciężkich importów)."""
import json
import os
import platform
import shutil
from pathlib import Path

PLIK_USTAWIEN = Path(__file__).resolve().parent / "settings.json"
KLUCZ_IMAGEMAGICK = "imagemagick_path"
IMAGEMAGICK_DOMYSLNA_WINDOWS = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"


def _domyslne_ustawienia():
    domyslna = IMAGEMAGICK_DOMYSLNA_WINDOWS if platform.system() == "Windows" else ""
    return {KLUCZ_IMAGEMAGICK: domyslna}


def wczytaj_ustawienia(plik=PLIK_USTAWIEN):
    """Wczytuje settings.json; brakujący lub uszkodzony plik daje ustawienia domyślne."""
    ustawienia = _domyslne_ustawienia()
    try:
        dane = json.loads(Path(plik).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return ustawienia
    if isinstance(dane, dict):
        ustawienia.update(dane)
    return ustawienia


def zapisz_ustawienia(ustawienia, plik=PLIK_USTAWIEN):
    plik = Path(plik)
    tymczasowy = plik.with_suffix(plik.suffix + ".tmp")
    tymczasowy.write_text(json.dumps(ustawienia, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tymczasowy.replace(plik)


def zapewnij_plik_ustawien(plik=PLIK_USTAWIEN):
    """Tworzy settings.json z wartościami domyślnymi (przeniesionymi z kodu), jeśli go nie ma."""
    if not Path(plik).exists():
        try:
            zapisz_ustawienia(_domyslne_ustawienia(), plik)
        except OSError:
            pass


def zapisana_sciezka_imagemagick(plik=PLIK_USTAWIEN):
    return str(wczytaj_ustawienia(plik).get(KLUCZ_IMAGEMAGICK) or "").strip()


def zapisz_sciezke_imagemagick(sciezka, plik=PLIK_USTAWIEN):
    ustawienia = wczytaj_ustawienia(plik)
    ustawienia[KLUCZ_IMAGEMAGICK] = str(sciezka).strip()
    zapisz_ustawienia(ustawienia, plik)


def znajdz_imagemagick(plik=PLIK_USTAWIEN):
    """Ścieżka z settings.json (jeśli plik istnieje), w przeciwnym razie magick/convert z PATH."""
    zapisana = zapisana_sciezka_imagemagick(plik)
    if zapisana and os.path.isfile(zapisana):
        return zapisana
    for nazwa in ("magick", "convert"):
        sciezka = shutil.which(nazwa)
        if sciezka:
            return sciezka
    return None
