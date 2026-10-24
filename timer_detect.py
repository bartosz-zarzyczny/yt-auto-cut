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
    blisko = np.zeros(pasmo.shape[1])
    for i in range(pasmo.shape[1]):
        lo, hi = max(idx[i] - 2, 0), idx[i] + 3
        blisko[i] = energia[lo:hi, i].sum()
    koncentracja = blisko / calkowita

    prog = np.percentile(amp, PERCENTYL_GLOSNOSCI)
    aktywne = (koncentracja > MIN_KONCENTRACJA) & (amp > prog)

    wyniki = []
    i, n = 0, len(aktywne)
    while i < n:
        if not aktywne[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and aktywne[j + 1] and abs(f_pik[j + 1] - f_pik[j]) <= MAX_SKOK_HZ:
            j += 1
        if j - i + 1 >= MIN_RAMEK:
            czestotliwosci = f_pik[i:j + 1]
            koncentracje = koncentracja[i:j + 1]
            if (np.median(koncentracje) >= MIN_KONCENTRACJA_SYGNALU
                    and np.std(czestotliwosci) <= MAX_ODCHYLENIE_CZESTOTLIWOSCI_HZ):
                wyniki.append((i * HOP / SR, float(np.median(czestotliwosci))))
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
