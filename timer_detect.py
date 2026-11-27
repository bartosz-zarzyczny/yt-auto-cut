import subprocess
from threading import Event
from typing import Callable, Optional

import numpy as np
from scipy.signal import stft
from system_settings import RED, RESET
from video_cancellation import GenerationCancelled

SR = 44100
N_FFT = 2048
HOP = 512
PASMO_MIN = 2000
PASMO_MAX = 3500
MIN_RAMEK = 22          # ok. 0,26 s ciągłego tonu (krótsze to zwykle tło)
MIN_KONCENTRACJA = 0.25  # udział energii pasma skupiony wokół piku
PERCENTYL_GLOSNOSCI = 90
MAX_SKOK_HZ = 60
MIN_KONCENTRACJA_SYGNALU = 0.85
MAX_ODCHYLENIE_CZESTOTLIWOSCI_HZ = 25
MAX_PRZERWA_RAMEK = 10        # ok. 0,12 s zagłuszenia tonu innym dźwiękiem nie przerywa sygnału
MIN_GLOSNOSC_PRZERWY = 0.3    # w przerwie ton musi mieć co najmniej 30% progu głośności
MIN_AKTYWNYCH_RAMEK = 12      # ok. 0,14 s czystego tonu w całym sygnale
MIN_KONCENTRACJA_TONU = 0.5   # wyraźny ton, choć cichszy od progu głośności, nadal należy do sygnału
MAX_ROZBIEG_RAMEK = 20        # do ok. 0,23 s narastania tonu przed pierwszą głośną ramką


def _wyciagnij_audio(sciezka_wideo, cancel_event: Optional[Event] = None):
    import imageio_ffmpeg
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", sciezka_wideo,
           "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    proces = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        try:
            surowe, blad = proces.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            if cancel_event and cancel_event.is_set():
                if proces.poll() is None:
                    proces.terminate()
                    try:
                        proces.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        proces.kill()
                        proces.communicate()
                raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
    if cancel_event and cancel_event.is_set():
        raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
    if proces.returncode:
        raise subprocess.CalledProcessError(
            proces.returncode, cmd, output=surowe, stderr=blad
        )
    return np.frombuffer(surowe, dtype=np.int16).astype(np.float32) / 32768.0


PEAK_HALF_WIDTH = 2  # liczba binów po każdej stronie piku wliczanych do koncentracji


def energy_near_peak(energy, peak_indices):
    """Suma energii w oknie +-PEAK_HALF_WIDTH binów wokół piku, dla każdej ramki naraz (bez pętli w Pythonie)."""
    padded = np.pad(energy, ((PEAK_HALF_WIDTH, PEAK_HALF_WIDTH), (0, 0)))
    columns = np.arange(energy.shape[1])
    return sum(
        padded[peak_indices + PEAK_HALF_WIDTH + offset, columns]
        for offset in range(-PEAK_HALF_WIDTH, PEAK_HALF_WIDTH + 1)
    )


def znajdz_sygnaly_timera(sciezka_wideo, cancel_event: Optional[Event] = None):
    """Zwraca listę (czas_s, częstotliwość_Hz) wykrytych sygnałów timera."""
    if cancel_event and cancel_event.is_set():
        raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
    y = _wyciagnij_audio(sciezka_wideo, cancel_event)
    if len(y) < N_FFT:
        return []

    freqs, _, Z = stft(y, fs=SR, nperseg=N_FFT, noverlap=N_FFT - HOP)
    if cancel_event and cancel_event.is_set():
        raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
    S = np.abs(Z)
    maska = (freqs >= PASMO_MIN) & (freqs <= PASMO_MAX)
    pasmo = S[maska, :]
    f_pasma = freqs[maska]

    idx = np.argmax(pasmo, axis=0)
    amp = pasmo[idx, np.arange(pasmo.shape[1])]
    f_pik = f_pasma[idx]

    energia = (pasmo ** 2)
    calkowita = energia.sum(axis=0) + 1e-12
    blisko = energy_near_peak(energia, idx)
    koncentracja = blisko / calkowita

    prog = np.percentile(amp, PERCENTYL_GLOSNOSCI)
    aktywne = (koncentracja > MIN_KONCENTRACJA) & (amp > prog)

    return _tone_runs(aktywne, amp, f_pik, koncentracja, prog)


def _tone_runs(aktywne, amp, f_pik, koncentracja, prog):
    """Ciągłe tony timera: (start_s, częstotliwość_Hz).

    Krótki szerokopasmowy dźwięk (krok, szelest, stuknięcie) potrafi na chwilę „zagłuszyć” ton —
    wtedy koncentracja energii spada, choć najsilniejsza częstotliwość pasma nadal jest ta sama.
    Takie ramki (do MAX_PRZERWA_RAMEK z rzędu) nie przerywają tonu, ale do jakości sygnału
    liczą się tylko ramki z czystym tonem."""
    wyniki = []
    i, n = 0, len(aktywne)
    min_glosnosc_przerwy = prog * MIN_GLOSNOSC_PRZERWY
    while i < n:
        if not aktywne[i]:
            i += 1
            continue
        def ton(k, czestotliwosc):
            """Ramka z tym samym, wyraźnym tonem — także trochę cichszym niż próg głośności."""
            return (abs(f_pik[k] - czestotliwosc) <= MAX_SKOK_HZ and amp[k] > min_glosnosc_przerwy
                    and (aktywne[k] or koncentracja[k] >= MIN_KONCENTRACJA_TONU))

        ostatnia, przerwa, k = i, 0, i + 1
        while k < n:
            if ton(k, f_pik[ostatnia]):
                ostatnia, przerwa = k, 0
            elif (abs(f_pik[k] - f_pik[ostatnia]) <= MAX_SKOK_HZ and amp[k] > min_glosnosc_przerwy
                    and przerwa < MAX_PRZERWA_RAMEK):
                przerwa += 1
            else:
                break
            k += 1
        j = ostatnia
        # Początek: cofamy się do narastania tonu (pierwsza głośna ramka bywa kilka ramek po starcie).
        s, cofniecie = i, 0
        while s > 0 and cofniecie < MAX_ROZBIEG_RAMEK and ton(s - 1, f_pik[i]):
            s, cofniecie = s - 1, cofniecie + 1
        czyste = np.flatnonzero(aktywne[s:j + 1]) + s
        if j - s + 1 >= MIN_RAMEK and len(czyste) >= MIN_AKTYWNYCH_RAMEK:
            czestotliwosci = f_pik[s:j + 1]
            if (np.median(koncentracja[czyste]) >= MIN_KONCENTRACJA_SYGNALU
                    and np.std(czestotliwosci) <= MAX_ODCHYLENIE_CZESTOTLIWOSCI_HZ):
                wyniki.append((s * HOP / SR, float(np.median(czestotliwosci))))
        i = j + 1
    return wyniki


def zglos_wykrycie_timera(
    sciezka_wideo,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Event] = None,
):
    """Wypisuje wynik wykrywania na konsoli (bez przycinania). Zwraca listę wykryć."""
    def raportuj(tekst, kolor=None):
        print(f"{kolor}{tekst}{RESET}" if kolor else tekst)
        if log_callback:
            log_callback(tekst)

    try:
        sygnaly = znajdz_sygnaly_timera(sciezka_wideo, cancel_event)
    except GenerationCancelled:
        raise
    except Exception as e:
        raportuj(f"[TIMER] Nie udało się przeanalizować dźwięku: {e}")
        return []

    if not sygnaly:
        raportuj("[TIMER] Nie wykryto sygnału timera.", RED)
    else:
        t, f = sygnaly[0]
        raportuj(f"[TIMER] Wykryto start timera: {t:.2f}s (~{f:.0f} Hz)")
        if len(sygnaly) > 1:
            raportuj(f"[TIMER] Pominięto {len(sygnaly) - 1} późniejszych sygnałów timera.")
    return sygnaly[:1]
