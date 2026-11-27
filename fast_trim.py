"""Szybkie przycięcie filmu bez ponownego kodowania obrazu (tryb „Tylko przycięcie”)."""
import subprocess
from pathlib import Path
from threading import Event
from typing import List, Optional, Tuple

from video_cancellation import GenerationCancelled

AUDIO_BITRATE = "192k"
POLL_SECONDS = 0.2


def ffmpeg_binary() -> str:
    """Ten sam FFmpeg, którego używa MoviePy (z settings MoviePy lub imageio-ffmpeg)."""
    from moviepy.config import get_setting

    return get_setting("FFMPEG_BINARY")


def probe_duration(path) -> float:
    """Długość filmu w sekundach odczytana z nagłówka (bez dekodowania klatek)."""
    from moviepy.video.io.ffmpeg_reader import ffmpeg_parse_infos

    duration = ffmpeg_parse_infos(str(path)).get("duration")
    if not duration:
        raise ValueError(f"Nie można odczytać długości filmu: {Path(path).name}")
    return float(duration)


def build_trim_command(
    ffmpeg: str, source, target, trim_range: Optional[Tuple[float, float]]
) -> List[str]:
    """Komenda FFmpeg: obraz kopiowany bez zmian, dźwięk kodowany do AAC (MP4 nie przyjmuje np. PCM z MOV).

    Przy kopiowaniu obrazu początek wypada na najbliższej wcześniejszej klatce kluczowej,
    więc film może zacząć się ułamek sekundy wcześniej niż wyliczony start."""
    command = [ffmpeg, "-hide_banner", "-v", "error", "-y"]
    if trim_range is not None:
        start, end = trim_range
        command += ["-ss", f"{start:.3f}", "-to", f"{end:.3f}"]
    command += [
        "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", AUDIO_BITRATE,
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        str(target),
    ]
    return command


def run_ffmpeg(command: List[str], cancel_event: Optional[Event] = None) -> None:
    """Uruchamia FFmpeg; przerwanie przez cancel_event kończy proces i zgłasza GenerationCancelled."""
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    while True:
        try:
            _, error_output = process.communicate(timeout=POLL_SECONDS)
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
    if process.returncode:
        message = error_output.decode("utf-8", errors="replace").strip().splitlines()
        raise RuntimeError("FFmpeg: " + (message[-1] if message else f"kod {process.returncode}"))


def trim_copy(
    source,
    target,
    trim_range: Optional[Tuple[float, float]],
    cancel_event: Optional[Event] = None,
) -> None:
    run_ffmpeg(build_trim_command(ffmpeg_binary(), source, target, trim_range), cancel_event)
