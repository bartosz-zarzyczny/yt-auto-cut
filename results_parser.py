"""Odczyt wyników zawodów (Practiscore, ECM, Trening) — bez ciężkich importów, używany też przez okno aplikacji."""
import os
import re
from typing import Dict, Tuple

TRYB_WYNIKOW_PRACTISCORE = "practiscore"
TRYB_WYNIKOW_ECM = "ecm"
TRYB_WYNIKOW_TRENING = "trening"
RESULTS_MODE_LABELS = {
    TRYB_WYNIKOW_PRACTISCORE: "Practiscore",
    TRYB_WYNIKOW_ECM: "ECM",
    TRYB_WYNIKOW_TRENING: "Trening",
}

WZORZEC_PRACTISCORE = re.compile(
    r"Stage\s+(\d+).*?(\d+)\s+([\d.]+%)\s+[\d.]+\s+(\d+)\s+([\d.]+)\s+([\d.]+)",
    re.IGNORECASE,
)
# Wiersz ECM: STG, FACTOR, PTS, A, C, D, MI, NS, PE, pusta kolumna, TIME
WZORZEC_ECM = re.compile(
    r"^[ \t]*Stage[ \t]+(\d+)[ \t]+([\d.]+)[ \t]+(\d+)(?:[ \t]+\d+){6}[ \t]+([\d.]+)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
# Wiersz ręcznie wpisany w formacie: numer toru; czas
WZORZEC_TRENING = re.compile(
    r"^[ \t]*(\d+)[ \t]*;[ \t]*(\d+(?:[.,]\d+)?)[ \t]*$",
    re.MULTILINE,
)


def _czytaj_wyniki_practiscore(tekst):
    wyniki = {}
    for dopasowanie in WZORZEC_PRACTISCORE.finditer(tekst):
        nr_toru = dopasowanie.group(1)
        wyniki[nr_toru] = {
            "miejsce": dopasowanie.group(2),
            "procent": dopasowanie.group(3),
            "punkty": dopasowanie.group(4),
            "hf": dopasowanie.group(5),
            "czas": float(dopasowanie.group(6)) # CZAS Z PRACTISCORE
        }
    return wyniki


def _czytaj_wyniki_ecm(tekst):
    wyniki = {}
    for dopasowanie in WZORZEC_ECM.finditer(tekst):
        nr_toru = str(int(dopasowanie.group(1)))
        wyniki[nr_toru] = {
            "miejsce": "",
            "procent": "",
            "punkty": dopasowanie.group(3),
            "hf": dopasowanie.group(2),
            "czas": float(dopasowanie.group(4)) # CZAS Z ECM
        }
    return wyniki


def _czytaj_wyniki_trening(tekst):
    wyniki = {}
    for dopasowanie in WZORZEC_TRENING.finditer(tekst):
        nr_toru = str(int(dopasowanie.group(1)))
        wyniki[nr_toru] = {
            "miejsce": "",
            "procent": "",
            "punkty": "",
            "hf": "",
            "czas": float(dopasowanie.group(2).replace(",", "."))
        }
    return wyniki


CZYTNIKI_WYNIKOW = {
    TRYB_WYNIKOW_PRACTISCORE: _czytaj_wyniki_practiscore,
    TRYB_WYNIKOW_ECM: _czytaj_wyniki_ecm,
    TRYB_WYNIKOW_TRENING: _czytaj_wyniki_trening,
}


def czytaj_wyniki_z_pliku(sciezka_do_pliku, tryb=TRYB_WYNIKOW_PRACTISCORE):
    if not os.path.exists(sciezka_do_pliku):
        print(f"Brak pliku z wynikami: {sciezka_do_pliku}")
        return {}

    czytnik = CZYTNIKI_WYNIKOW.get(tryb)
    if czytnik is None:
        raise ValueError(f"Nieznany tryb wyników: {tryb}")

    with open(sciezka_do_pliku, 'r', encoding='utf-8') as f:
        tekst = f.read()

    return czytnik(tekst)


def parse_results(text: str, mode: str) -> Dict[str, dict]:
    """Wyniki z tekstu w danym formacie: {numer_toru: {miejsce, procent, punkty, hf, czas}}."""
    reader = CZYTNIKI_WYNIKOW.get(mode)
    if reader is None:
        raise ValueError(f"Nieznany tryb wyników: {mode}")
    return reader(text)


def detect_results_mode(text: str, preferred: str = TRYB_WYNIKOW_PRACTISCORE) -> Tuple[str, Dict[str, dict]]:
    """Wybiera format, który odczytuje najwięcej torów; przy remisie wygrywa preferowany."""
    best_mode, best = preferred, parse_results(text, preferred)
    for mode in CZYTNIKI_WYNIKOW:
        results = parse_results(text, mode)
        if len(results) > len(best):
            best_mode, best = mode, results
    return best_mode, best
