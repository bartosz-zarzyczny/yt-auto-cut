"""Montaż jednym poleceniem FFmpeg: przycięcie, skalowanie, nakładki (napisy, logo) i muzyka.

Zastępuje renderowanie klatka po klatce w MoviePy — obraz nie przechodzi przez Pythona, więc montaż
jest kilka razy szybszy, a postęp jest odczytywany z FFmpeg (-progress)."""
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, List, Optional, Sequence, Tuple, Union

from video_cancellation import GenerationCancelled

FPS = 30
AUDIO_RATE = 44100
AUDIO_BITRATE = "192k"
MUSIC_FADE_OUT = 1.0
TEXT_FADE = 0.4
POSITION_CENTER = "center"

# Jakość dobrana do kodeka (zamiast stałego bitrate). AMF i QSV nie były testowane na sprzęcie,
# więc zostają przy bitrate jak dotąd.
CODEC_QUALITY_ARGS = {
    "libx264": ["-preset", "fast", "-crf", "20"],
    "h264_nvenc": ["-preset", "fast", "-rc", "vbr", "-cq", "21", "-b:v", "0"],
    "h264_videotoolbox": ["-q:v", "65", "-allow_sw", "1"],
    "h264_amf": ["-quality", "speed", "-b:v", "8000k"],
    "h264_qsv": ["-preset", "fast", "-b:v", "8000k"],
}
DEFAULT_QUALITY_ARGS = ["-b:v", "8000k"]


@dataclass
class Overlay:
    """Obraz RGBA nakładany na film od `start` do `end` (sekundy), opcjonalnie z płynnym pojawieniem się."""
    image: object                      # PIL.Image (RGBA)
    x: Union[int, str]                 # piksele albo POSITION_CENTER
    y: int
    start: float
    end: float
    fade: bool = False


@dataclass
class RenderJob:
    source: Path
    output: Path
    resolution: Tuple[int, int]
    duration: float                     # długość wyniku w sekundach
    trim_start: float = 0.0
    has_audio: bool = True
    music: Optional[Path] = None
    music_volume: float = 0.12
    overlays: Sequence[Overlay] = ()
    codec: str = "libx264"


def quality_args(codec: str) -> List[str]:
    return list(CODEC_QUALITY_ARGS.get(codec, DEFAULT_QUALITY_ARGS))


def _overlay_x(overlay: Overlay) -> str:
    return "(main_w-overlay_w)/2" if overlay.x == POSITION_CENTER else str(int(overlay.x))


def build_command(ffmpeg: str, job: RenderJob, overlay_files: Sequence[Path]) -> List[str]:
    """Pełne polecenie FFmpeg dla zadania; overlay_files to PNG odpowiadające job.overlays."""
    width, height = job.resolution
    duration = f"{job.duration:.3f}"
    command = [ffmpeg, "-hide_banner", "-v", "error", "-y", "-nostats", "-progress", "pipe:1"]
    command += ["-ss", f"{job.trim_start:.3f}", "-t", duration, "-i", str(job.source)]
    for path in overlay_files:
        command += ["-loop", "1", "-framerate", str(FPS), "-t", duration, "-i", str(path)]
    music_index = None
    if job.music is not None:
        music_index = 1 + len(overlay_files)
        command += ["-stream_loop", "-1", "-i", str(job.music)]

    # Obraz: skalowanie do rozdzielczości wyjściowej (jak dotąd, bez kadrowania), potem nakładki.
    filters = [f"[0:v]scale={width}:{height},setsar=1,fps={FPS}[v0]"]
    for index, overlay in enumerate(job.overlays):
        source = f"[{index + 1}:v]format=rgba"
        if overlay.fade:
            fade_out = max(overlay.start, overlay.end - TEXT_FADE)
            source += (f",fade=t=in:st={overlay.start:.3f}:d={TEXT_FADE}:alpha=1"
                       f",fade=t=out:st={fade_out:.3f}:d={TEXT_FADE}:alpha=1")
        filters.append(f"{source}[o{index}]")
        filters.append(
            f"[v{index}][o{index}]overlay=x={_overlay_x(overlay)}:y={int(overlay.y)}"
            f":enable='between(t,{overlay.start:.3f},{overlay.end:.3f})':eof_action=pass[v{index + 1}]"
        )
    filters.append(f"[v{len(job.overlays)}]format=yuv420p[vout]")

    # Dźwięk: oryginał + zapętlona, ściszona muzyka z wyciszeniem na końcu.
    audio_label = None
    if music_index is not None:
        fade_start = max(0.0, job.duration - MUSIC_FADE_OUT)
        filters.append(
            f"[{music_index}:a]volume={job.music_volume},atrim=0:{duration},asetpts=PTS-STARTPTS,"
            f"afade=t=out:st={fade_start:.3f}:d={MUSIC_FADE_OUT},aresample={AUDIO_RATE}[music]"
        )
        if job.has_audio:
            filters.append(f"[0:a]aresample={AUDIO_RATE}[orig]")
            filters.append("[orig][music]amix=inputs=2:duration=first:normalize=0[aout]")
        else:
            filters.append("[music]anull[aout]")
        audio_label = "[aout]"

    command += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if audio_label:
        command += ["-map", audio_label]
    elif job.has_audio:
        command += ["-map", "0:a:0"]
    command += ["-c:v", job.codec, *quality_args(job.codec), "-pix_fmt", "yuv420p", "-r", str(FPS)]
    if audio_label or job.has_audio:
        command += ["-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE)]
    command += ["-t", duration, "-movflags", "+faststart", str(job.output)]
    return command


def _progress_seconds(line: str) -> Optional[float]:
    """Czas z linii -progress (out_time_us / out_time_ms są w mikrosekundach)."""
    key, _, value = line.strip().partition("=")
    if key in ("out_time_us", "out_time_ms") and value.lstrip("-").isdigit():
        return max(0, int(value)) / 1_000_000
    return None


def run(
    ffmpeg: str,
    job: RenderJob,
    cancel_event: Optional[Event] = None,
    on_progress: Optional[Callable[[float], None]] = None,
) -> None:
    """Renderuje film; przerwanie przez cancel_event kończy FFmpeg i zgłasza GenerationCancelled."""
    with tempfile.TemporaryDirectory(prefix="automato_") as directory:
        overlay_files = []
        for index, overlay in enumerate(job.overlays):
            path = Path(directory) / f"overlay_{index}.png"
            overlay.image.save(path)
            overlay_files.append(path)
        command = build_command(ffmpeg, job, overlay_files)
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace"
        )
        errors: List[str] = []
        reader = threading.Thread(target=lambda: errors.extend(process.stderr), daemon=True)
        reader.start()
        cancel = cancel_event or Event()
        watcher = threading.Thread(target=_terminate_on_cancel, args=(process, cancel), daemon=True)
        watcher.start()
        last_reported = -1.0
        for line in process.stdout:
            seconds = _progress_seconds(line)
            if seconds is None or on_progress is None or job.duration <= 0:
                continue
            fraction = min(1.0, seconds / job.duration)
            if fraction - last_reported >= 0.005:
                last_reported = fraction
                on_progress(fraction)
        process.wait()
        reader.join(timeout=5)
        if cancel.is_set():
            raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
        if process.returncode:
            message = "".join(errors).strip().splitlines()
            raise RuntimeError("FFmpeg: " + (message[-1] if message else f"kod {process.returncode}"))
        if on_progress is not None:
            on_progress(1.0)


def _terminate_on_cancel(process: subprocess.Popen, cancel_event: Event) -> None:
    while process.poll() is None:
        if cancel_event.wait(0.2):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            return
