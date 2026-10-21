import argparse
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple, Union

KATALOG_PROJEKTU = Path(__file__).resolve().parent
PLIK_OPISU = KATALOG_PROJEKTU / "opis_zawodow.txt"
MAKS_DLUGOSC_TYTULU = 100

_MIESIACE = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9,
    "października": 10, "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}


@dataclass(frozen=True)
class DaneZawodow:
    nazwa: str
    data: date
    lokalizacja: str
    typ: str
    poziom: str


def _parsuj_date(tekst: str) -> Optional[date]:
    for wzorzec, kolejnosc in (
        (r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", "ymd"),
        (r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", "dmy"),
    ):
        dopasowanie = re.search(wzorzec, tekst)
        if dopasowanie:
            wartosci = [int(wartosc) for wartosc in dopasowanie.groups()]
            rok, miesiac, dzien = (
                wartosci if kolejnosc == "ymd" else (wartosci[2], wartosci[1], wartosci[0])
            )
            try:
                return date(rok, miesiac, dzien)
            except ValueError as blad:
                raise ValueError(f"Nieprawidłowa data zawodów: {dopasowanie.group(0)}") from blad

    miesiac_wzorzec = "|".join(sorted(_MIESIACE, key=len, reverse=True))
    dopasowanie = re.search(
        rf"\b({miesiac_wzorzec})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})\b",
        tekst,
        re.IGNORECASE,
    )
    if dopasowanie:
        miesiac = _MIESIACE[dopasowanie.group(1).lower()]
        return date(int(dopasowanie.group(3)), miesiac, int(dopasowanie.group(2)))

    dopasowanie = re.search(
        rf"\b(\d{{1,2}})\s+({miesiac_wzorzec})\s+(\d{{4}})\b", tekst, re.IGNORECASE
    )
    if dopasowanie:
        miesiac = _MIESIACE[dopasowanie.group(2).lower()]
        return date(int(dopasowanie.group(3)), miesiac, int(dopasowanie.group(1)))
    return None


def _wartosc_pola(linie: List[str], wzorzec: str) -> str:
    for linia in linie:
        dopasowanie = re.match(wzorzec + r"\s*:\s*(.+?)\s*$", linia, re.IGNORECASE)
        if dopasowanie:
            return dopasowanie.group(1).strip()
    return ""


def czytaj_dane_zawodow(sciezka_opisu: Path = PLIK_OPISU) -> DaneZawodow:
    if not sciezka_opisu.is_file():
        raise FileNotFoundError(f"Brak pliku z opisem zawodów: {sciezka_opisu}")

    tekst = sciezka_opisu.read_text(encoding="utf-8-sig")
    linie = [linia.strip() for linia in tekst.splitlines()]
    nazwa = _wartosc_pola(linie, r"(?:Nazwa zawodów|Competition name|Match name)")
    if not nazwa:
        nazwa = next((linia for linia in linie if linia), "")
    if not nazwa:
        raise ValueError(f"Plik z opisem zawodów jest pusty: {sciezka_opisu}")

    data_zawodow = None
    for linia in linie:
        if re.search(r"\b(?:Match starts|Main Match|Data zawodów|Data|Termin)\b", linia, re.I):
            data_zawodow = _parsuj_date(linia)
            if data_zawodow:
                break
    if data_zawodow is None:
        raise ValueError(
            f"Nie znaleziono daty zawodów w {sciezka_opisu}; "
            "podaj ją w polu Data zawodów lub Match starts."
        )

    lokalizacja = _wartosc_pola(linie, r"(?:Miejsce|Location)")
    if not lokalizacja:
        for indeks, linia in enumerate(linie):
            if re.match(r"Location\s*:\s*$", linia, re.IGNORECASE):
                lokalizacja = next((wartosc for wartosc in linie[indeks + 1:] if wartosc), "")
                break
    typ = _wartosc_pola(linie, r"(?:Typ zawodów(?:/Match type)?|Match type)")
    poziom = _wartosc_pola(linie, r"(?:Poziom(?:/Match level)?|Match level)")
    return DaneZawodow(nazwa, data_zawodow, lokalizacja, typ, poziom)


def generuj_tytul(
    nazwa_pliku: Union[str, Path], sciezka_opisu: Path = PLIK_OPISU
) -> str:
    dane = czytaj_dane_zawodow(sciezka_opisu)
    dopasowanie = re.search(r"(?:stage|tor)[\s_-]*(\d+)", Path(nazwa_pliku).stem, re.IGNORECASE)
    if not dopasowanie:
        raise ValueError(
            f"Nie można odczytać numeru toru z nazwy pliku {Path(nazwa_pliku).name}; "
            "oczekiwano np. Gotowe_Stage_3.mp4."
        )

    stala_czesc = f"{dane.data.isoformat()} -  - Tor {dopasowanie.group(1)} #bodycam"
    limit_nazwy = MAKS_DLUGOSC_TYTULU - len(stala_czesc)
    if limit_nazwy < 1:
        raise ValueError("Data i numer toru nie mieszczą się w limicie długości tytułu YouTube.")
    nazwa = dane.nazwa[:limit_nazwy].rstrip()
    return f"{dane.data.isoformat()} - {nazwa} - Tor {dopasowanie.group(1)} #bodycam"


def _slug_hashtagu(tekst: str) -> str:
    tekst = tekst.replace("Ł", "L").replace("ł", "l")
    ascii_tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode("ascii")
    slowa = re.findall(r"[A-Za-z][A-Za-z0-9]*", ascii_tekst)
    return "".join(slowa)


def generuj_opis_i_hashtagi(
    sciezka_opisu: Path = PLIK_OPISU,
) -> Tuple[str, List[str]]:
    dane = czytaj_dane_zawodow(sciezka_opisu)
    hashtagi = ["#IPSC"]
    for fraza in (dane.typ, dane.lokalizacja, dane.nazwa):
        for slowo in re.findall(r"[^\W\d_]+", fraza, re.UNICODE):
            hashtag = _slug_hashtagu(slowo)
            if len(hashtag) >= 3 and hashtag.casefold() not in {
                tag[1:].casefold() for tag in hashtagi
            }:
                hashtagi.append(f"#{hashtag}")
            if len(hashtagi) >= 8:
                break
        if len(hashtagi) >= 8:
            break

    linie_opisu = [dane.nazwa, f"Data zawodów: {dane.data.isoformat()}"]
    if dane.lokalizacja:
        linie_opisu.append(f"Miejsce: {dane.lokalizacja}")
    if dane.typ:
        linie_opisu.append(f"Typ zawodów: {dane.typ}")
    if dane.poziom:
        linie_opisu.append(f"Poziom: {dane.poziom}")
    return "\n".join(linie_opisu + ["", " ".join(hashtagi)]), hashtagi


def bezpieczna_nazwa_pliku(tytul: str, rozszerzenie: str) -> str:
    nazwa = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", tytul)
    nazwa = re.sub(r"\s+", " ", nazwa).strip(" .")
    return f"{nazwa}{rozszerzenie.lower()}"


def przemianuj_plik(sciezka: Path, tytul: str) -> Path:
    cel = sciezka.with_name(bezpieczna_nazwa_pliku(tytul, sciezka.suffix))
    if cel == sciezka:
        return sciezka
    if cel.exists():
        raise FileExistsError(f"Plik docelowy już istnieje: {cel}")
    return sciezka.rename(cel)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nadaje filmowi nazwę według danych zawodów.")
    parser.add_argument("plik", type=Path, help="Plik MP4 zawierający numer toru w nazwie.")
    parser.add_argument("--opis", type=Path, default=PLIK_OPISU, help="Plik z opisem zawodów.")
    args = parser.parse_args()

    tytul = generuj_tytul(args.plik, args.opis)
    nowa_sciezka = przemianuj_plik(args.plik, tytul)
    print(f"Tytuł: {tytul}")
    print(f"Plik: {nowa_sciezka}")


if __name__ == "__main__":
    main()
