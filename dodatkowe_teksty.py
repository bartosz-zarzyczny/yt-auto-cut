import re
import os

from moviepy.editor import TextClip

MAX_TEKSTOW = 5
MIN_CZAS_TEKSTU = 5.0     # s
MAX_CZAS_TEKSTU = 8.0     # s
MIN_PRZERWA = 2.0         # s
START_OFFSET = 1.0        # s od początku filmu do pierwszego tekstu
KONIEC_MARGINES = 1.0     # s wolne na końcu filmu
CZCIONKA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Fonts", "Oxanium", "static", "Oxanium-Bold.ttf").replace("\\", "/")
KOLOR = "#00F0FF"         # neonowy cyjan
KOLOR_OBRYSU = "#1A0536"
SZEROKOSC = 960


def czytaj_teksty(sciezka):
    """Zwraca do MAX_TEKSTOW niepustych tekstów z nawiasów [ ] w pliku."""
    if not os.path.exists(sciezka):
        print(f"[TEKSTY] Brak pliku z tekstami: {sciezka}")
        return []
    with open(sciezka, "r", encoding="utf-8") as f:
        zawartosc = f.read()
    teksty = [" ".join(t.split()) for t in re.findall(r"\[([^\]]*)\]", zawartosc)]
    return [t for t in teksty if t][:MAX_TEKSTOW]


def planuj_czasy(liczba_tekstow, dlugosc_filmu):
    """Zwraca listę (start, czas_trwania): teksty po kolei, z przerwami, tyle ile się zmieści."""
    dostepny = dlugosc_filmu - START_OFFSET - KONIEC_MARGINES
    n = min(liczba_tekstow, MAX_TEKSTOW)
    while n > 0 and n * MIN_CZAS_TEKSTU + (n - 1) * MIN_PRZERWA > dostepny:
        n -= 1
    if n == 0:
        return []
    # Równe "sloty" na całe okno: teksty rozłożone równomiernie, przerwy >= MIN_PRZERWA
    slot = dostepny / n
    czas = min(MAX_CZAS_TEKSTU, max(MIN_CZAS_TEKSTU, slot - MIN_PRZERWA))
    margines = (slot - czas) / 2
    return [(START_OFFSET + i * slot + margines, czas) for i in range(n)]


def utworz_klipy_tekstowe(sciezka, dlugosc_filmu):
    """Zwraca listę TextClip do nałożenia w górnej części wideo."""
    teksty = czytaj_teksty(sciezka)
    plan = planuj_czasy(len(teksty), dlugosc_filmu)
    if len(plan) < len(teksty):
        print(f"[TEKSTY] Film za krótki - użyto {len(plan)} z {len(teksty)} tekstów.")
    klipy = []
    for tekst, (start, czas) in zip(teksty, plan):
        klip = TextClip(tekst, fontsize=60, color=KOLOR, font=CZCIONKA,
                        stroke_color=KOLOR_OBRYSU, stroke_width=2, method="caption",
                        size=(SZEROKOSC, None), align="center")
        klip = (klip.set_start(start).set_duration(czas)
                .set_position(("center", 0.07), relative=True)
                .crossfadein(0.4).crossfadeout(0.4))
        klipy.append(klip)
        print(f"[TEKSTY] \"{tekst}\": {start:.1f}s - {start + czas:.1f}s")
    return klipy
