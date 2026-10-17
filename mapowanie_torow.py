import os


def czytaj_kolejnosc_torow(sciezka_do_pliku):
    """Zwraca listę numerów torów (str) w kolejności z pliku tory.txt.
    N-ta linia = numer toru dla N-tego pliku wideo (po sortowaniu)."""
    if not os.path.exists(sciezka_do_pliku):
        print(f"Brak pliku z kolejnością torów: {sciezka_do_pliku}")
        return []

    with open(sciezka_do_pliku, 'r', encoding='utf-8-sig') as f:
        return [linia.strip() for linia in f if linia.strip()]


def przypisz_tory(wideo_pliki, sciezka_do_pliku_tory):
    """Zwraca listę (nazwa_pliku, nr_toru). Gdy brak pliku lub wpisu w tory.txt,
    używa numeru wynikającego z pozycji w sortowaniu."""
    kolejnosc = czytaj_kolejnosc_torow(sciezka_do_pliku_tory)
    wynik = []
    for index, nazwa in enumerate(sorted(wideo_pliki)):
        nr_toru = kolejnosc[index] if index < len(kolejnosc) else str(index + 1)
        wynik.append((nazwa, nr_toru))
    return wynik
