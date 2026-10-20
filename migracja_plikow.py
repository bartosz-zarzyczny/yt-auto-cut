"""Zmiana nazw plików tekstowych projektu (bez ciężkich importów)."""
from pathlib import Path

STARE_NAZWY = {
    "wynik2.txt": "wyniki.txt",
    "tory.txt": "mapowanie_torow.txt",
    "dodatkowe_teksty.txt": "teksty_wideo.txt",
}


def przenies_stare_pliki(katalog):
    """Zmienia nazwy starych plików na nowe, o ile nowego jeszcze nie ma."""
    katalog = Path(katalog)
    for stara, nowa in STARE_NAZWY.items():
        stary_plik, nowy_plik = katalog / stara, katalog / nowa
        if stary_plik.exists() and not nowy_plik.exists():
            try:
                stary_plik.rename(nowy_plik)
            except OSError:
                pass


def popraw_sciezke(sciezka):
    """Zapisaną w ustawieniach starą nazwę pliku zamienia na nową."""
    plik = Path(str(sciezka))
    nowa = STARE_NAZWY.get(plik.name.lower())
    return str(plik.with_name(nowa)) if nowa else str(sciezka)
