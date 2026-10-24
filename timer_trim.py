from typing import Callable, Optional

from system_settings import RED, RESET

BEFORE_START = 0.5   # o tyle cofamy się względem wykrytego sygnału
AFTER_END = 0.8      # zapas po czasie przebiegu


def determine_trim(signals, run_time: Optional[float], video_length):
    """Zwraca (start, end) w sekundach lub None, gdy nie ma jednoznacznego wykrycia."""
    if run_time is None or len(signals) != 1:
        return None

    signal_time = signals[0][0]
    start = max(0.0, signal_time - BEFORE_START)
    end = start + run_time + BEFORE_START + AFTER_END
    end = min(end, video_length)
    if end <= start:
        return None
    return start, end


def trim_video(
    video,
    signals,
    run_time: Optional[float],
    log_callback: Optional[Callable[[str], None]] = None,
):
    """Przycina klip do przebiegu i wypisuje informację na konsoli."""
    def report(text, kolor=None):
        print(f"{kolor}{text}{RESET}" if kolor else text)
        if log_callback:
            log_callback(text)

    if run_time is None:
        report("[PRZYCIĘCIE] Pominięto - brak czasu przebiegu w wynikach, zostaje pełny film.")
        return video

    result = determine_trim(signals, run_time, video.duration)
    if result is None:
        report("[PRZYCIĘCIE] Pominięto - brak jednoznacznego wykrycia timera, zostaje pełny film.", RED)
        return video

    start, end = result
    report(f"[PRZYCIĘCIE] {start:.2f}s -> {end:.2f}s (czas przebiegu {run_time:.2f}s)")
    return video.subclip(start, end)
