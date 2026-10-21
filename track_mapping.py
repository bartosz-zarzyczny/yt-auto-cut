from kolejnosc_torow import czytaj_kolejnosc_torow, ROZDZIELCZOSC_DOMYSLNA


def przypisz_tory(wideo_pliki, sciezka_do_pliku_tory, rozdzielczosc_domyslna=ROZDZIELCZOSC_DOMYSLNA):
    """Zwraca listę (nazwa_pliku, nr_toru, rozdzielczosc). Gdy brak pliku lub wpisu w mapowanie_torow.txt,
    używa numeru wynikającego z pozycji w sortowaniu. Plik bez litery H/V dostaje rozdzielczość domyślną."""
    kolejnosc = czytaj_kolejnosc_torow(sciezka_do_pliku_tory, rozdzielczosc_domyslna)
    wynik = []
    for index, nazwa in enumerate(sorted(wideo_pliki)):
        if index < len(kolejnosc):
            nr_toru, rozdzielczosc = kolejnosc[index]
        else:
            nr_toru, rozdzielczosc = str(index + 1), rozdzielczosc_domyslna
        wynik.append((nazwa, nr_toru, rozdzielczosc))
    return wynik
