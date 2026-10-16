import subprocess

import numpy as np
from scipy.signal import stft

SR = 44100
N_FFT = 2048
HOP = 512
PASMO_MIN = 2000
PASMO_MAX = 3500
MIN_RAMEK = 22          # ok. 0,26 s ciągłego tonu (krótsze to zwykle tło)
MIN_KONCENTRACJA = 0.25  # udział energii pasma skupiony wokół piku
PERCENTYL_GLOSNOSCI = 90
MAX_SKOK_HZ = 60


def _wyciagnij_audio(sciezka_wideo):
    import imageio_ffmpeg
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", sciezka_wideo,
           "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    surowe = subprocess.run(cmd, stdout=subprocess.PIPE, check=True).stdout
    return np.frombuffer(surowe, dtype=np.int16).astype(np.float32) / 32768.0


def znajdz_sygnaly_timera(sciezka_wideo):
    """Zwraca listę (czas_s, częstotliwość_Hz) wykrytych sygnałów timera."""
    y = _wyciagnij_audio(sciezka_wideo)
    if len(y) < N_FFT:
        return []

    freqs, _, Z = stft(y, fs=SR, nperseg=N_FFT, noverlap=N_FFT - HOP)
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
            wyniki.append((i * HOP / SR, float(np.median(f_pik[i:j + 1]))))
        i = j + 1
    return wyniki


def zglos_wykrycie_timera(sciezka_wideo):
    """Wypisuje wynik wykrywania na konsoli (bez przycinania). Zwraca listę wykryć."""
    try:
        sygnaly = znajdz_sygnaly_timera(sciezka_wideo)
    except Exception as e:
        print(f"[TIMER] Nie udało się przeanalizować dźwięku: {e}")
        return []

    if not sygnaly:
        print("[TIMER] Nie wykryto sygnału timera.")
    elif len(sygnaly) == 1:
        t, f = sygnaly[0]
        print(f"[TIMER] Wykryto start timera: {t:.2f}s (~{f:.0f} Hz)")
    else:
        lista = ", ".join(f"{t:.2f}s (~{f:.0f} Hz)" for t, f in sygnaly)
        print("!" * 70)
        print(f"!!! UWAGA: WIELE WYKRYĆ TIMERA ({len(sygnaly)}) W JEDNYM PLIKU !!!")
        print(f"!!! {lista}")
        print("!!! Sprawdź ręcznie, który sygnał jest startowy.")
        print("!" * 70)
    return sygnaly
