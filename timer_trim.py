from typing import Callable, Optional

PRZED_STARTEM = 0.5   # o tyle cofamy się względem wykrytego sygnału
PO_KONCU = 0.8        # zapas po czasie przebiegu


def wyznacz_przyciecie(sygnaly, czas_przebiegu, dlugosc_wideo):
    """Zwraca (start, koniec) w sekundach lub None, gdy nie ma jednoznacznego wykrycia."""
    if len(sygnaly) != 1:
        return None

    t_sygnalu = sygnaly[0][0]
    start = max(0.0, t_sygnalu - PRZED_STARTEM)
    koniec = start + czas_przebiegu + PRZED_STARTEM + PO_KONCU
    koniec = min(koniec, dlugosc_wideo)
    if koniec <= start:
        return None
    return start, koniec


def przytnij_wideo(
    video, sygnaly, czas_przebiegu, log_callback: Optional[Callable[[str], None]] = None
):
    """Przycina klip do przebiegu i wypisuje informację na konsoli."""
    def raportuj(tekst):
        print(tekst)
        if log_callback:
            log_callback(tekst)

    wynik = wyznacz_przyciecie(sygnaly, czas_przebiegu, video.duration)
    if wynik is None:
        raportuj("[PRZYCIĘCIE] Pominięto - brak jednoznacznego wykrycia timera, zostaje pełny film.")
        return video

    start, koniec = wynik
    raportuj(f"[PRZYCIĘCIE] {start:.2f}s -> {koniec:.2f}s (czas przebiegu {czas_przebiegu:.2f}s)")
    return video.subclip(start, koniec)
