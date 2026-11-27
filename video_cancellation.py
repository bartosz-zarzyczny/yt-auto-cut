from threading import Event
from typing import Callable, Optional

from proglog import ProgressBarLogger

# Pasek klatek wideo w write_videofile MoviePy (dźwięk ma osobny pasek "chunk").
VIDEO_FRAMES_BAR = "t"
PROGRESS_STEP = 0.005  # nie zgłaszamy częściej niż co 0,5%


class GenerationCancelled(Exception):
    pass


class CancellableProgressLogger(ProgressBarLogger):
    def __init__(self, cancel_event: Event, on_progress: Optional[Callable[[float], None]] = None):
        super().__init__()
        self.cancel_event = cancel_event
        self.on_progress = on_progress
        self.last_progress = None
        self._last_reported = -1.0

    def __call__(self, **kwargs):
        self._raise_if_cancelled()
        super().__call__(**kwargs)

    def bars_callback(self, bar, attr, value, old_value=None):
        self.last_progress = (bar, attr, value, old_value)
        self._raise_if_cancelled()
        if self.on_progress is None or bar != VIDEO_FRAMES_BAR or attr != "index":
            return
        total = self.bars.get(bar, {}).get("total")
        if not total:
            return
        fraction = min(1.0, (value + 1) / total)
        if fraction - self._last_reported >= PROGRESS_STEP or fraction >= 1.0:
            self._last_reported = fraction
            self.on_progress(fraction)

    def _raise_if_cancelled(self):
        if self.cancel_event.is_set():
            raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
