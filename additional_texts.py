import re
import os
from typing import Callable, Optional

from moviepy.editor import TextClip

MAX_TEXTS = 5
MIN_TEXT_DURATION = 5.0     # s
MAX_TEXT_DURATION = 8.0     # s
MIN_GAP = 2.0               # s
START_OFFSET = 1.0          # s od początku filmu do pierwszego tekstu
END_MARGIN = 1.0            # s wolne na końcu filmu
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Fonts", "mister-brush", "MisterBrush.ttf").replace("\\", "/")
COLOR = "#00F0FF"           # neonowy cyjan
OUTLINE_COLOR = "#1A0536"
WIDTH = 960


def read_texts(path):
    """Zwraca do MAX_TEXTS niepustych tekstów z nawiasów [ ] w pliku."""
    if not os.path.exists(path):
        print(f"[TEKSTY] Brak pliku z tekstami: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    texts = [" ".join(t.split()) for t in re.findall(r"\[([^\]]*)\]", content)]
    return [t for t in texts if t][:MAX_TEXTS]


def plan_timings(text_count, video_length):
    """Zwraca listę (start, czas_trwania): teksty po kolei, z przerwami, tyle ile się zmieści."""
    available = video_length - START_OFFSET - END_MARGIN
    n = min(text_count, MAX_TEXTS)
    while n > 0 and n * MIN_TEXT_DURATION + (n - 1) * MIN_GAP > available:
        n -= 1
    if n == 0:
        return []
    # Równe "sloty" na całe okno: teksty rozłożone równomiernie, przerwy >= MIN_GAP
    slot = available / n
    duration = min(MAX_TEXT_DURATION, max(MIN_TEXT_DURATION, slot - MIN_GAP))
    margin = (slot - duration) / 2
    return [(START_OFFSET + i * slot + margin, duration) for i in range(n)]


def create_text_clips(
    path, video_length, log_callback: Optional[Callable[[str], None]] = None
):
    """Zwraca listę TextClip do nałożenia w górnej części wideo."""
    def report(text):
        print(text)
        if log_callback:
            log_callback(text)

    texts = read_texts(path)
    plan = plan_timings(len(texts), video_length)
    if len(plan) < len(texts):
        report(f"[TEKSTY] Film za krótki - użyto {len(plan)} z {len(texts)} tekstów.")
    clips = []
    for text, (start, duration) in zip(texts, plan):
        clip = TextClip(text, fontsize=60, color=COLOR, font=FONT_PATH,
                        stroke_color=OUTLINE_COLOR, stroke_width=2, method="caption",
                        size=(WIDTH, None), align="center")
        clip = (clip.set_start(start).set_duration(duration)
                .set_position(("center", 0.07), relative=True)
                .crossfadein(0.4).crossfadeout(0.4))
        clips.append(clip)
        report(f"[TEKSTY] \"{text}\": {start:.1f}s - {start + duration:.1f}s")
    return clips
