import os

ROZDZIELCZOSC_DOMYSLNA = (1080, 1920)
ROZDZIELCZOSCI = {"H": (1920, 1080), "V": (1080, 1920)}


def czytaj_kolejnosc_torow(sciezka_do_pliku, domyslna=ROZDZIELCZOSC_DOMYSLNA):
    """Zwraca listę (nr_toru, (szer, wys)) w kolejności z mapowanie_torow.txt.
    Format linii: "numer" lub "numer;H" / "numer;V". Bez litery używana jest rozdzielczość `domyslna`."""
    if not os.path.exists(sciezka_do_pliku):
        print(f"Brak pliku z kolejnością torów: {sciezka_do_pliku}")
        return []

    wynik = []
    with open(sciezka_do_pliku, 'r', encoding='utf-8-sig') as f:
        for linia in f:
            linia = linia.strip()
            if not linia:
                continue
            nr_toru, _, orientacja = linia.partition(";")
            rozdzielczosc = ROZDZIELCZOSCI.get(orientacja.strip().upper(), domyslna)
            wynik.append((nr_toru.strip(), rozdzielczosc))
    return wynik
