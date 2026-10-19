from kolejnosc_torow import czytaj_kolejnosc_torow, ROZDZIELCZOSC_DOMYSLNA


def przypisz_tory(wideo_pliki, sciezka_do_pliku_tory):
    """Zwraca listę (nazwa_pliku, nr_toru, rozdzielczosc). Gdy brak pliku lub wpisu w tory.txt,
    używa numeru wynikającego z pozycji w sortowaniu i rozdzielczości domyślnej."""
    kolejnosc = czytaj_kolejnosc_torow(sciezka_do_pliku_tory)
    wynik = []
    for index, nazwa in enumerate(sorted(wideo_pliki)):
        if index < len(kolejnosc):
            nr_toru, rozdzielczosc = kolejnosc[index]
        else:
            nr_toru, rozdzielczosc = str(index + 1), ROZDZIELCZOSC_DOMYSLNA
        wynik.append((nazwa, nr_toru, rozdzielczosc))
    return wynik
