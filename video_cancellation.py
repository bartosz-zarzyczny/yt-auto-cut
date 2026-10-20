from threading import Event

from proglog import ProgressBarLogger


class GenerationCancelled(Exception):
    pass


class CancellableProgressLogger(ProgressBarLogger):
    def __init__(self, cancel_event: Event):
        super().__init__()
        self.cancel_event = cancel_event
        self.last_progress = None

    def __call__(self, **kwargs):
        self._raise_if_cancelled()
        super().__call__(**kwargs)

    def bars_callback(self, bar, attr, value, old_value=None):
        self.last_progress = (bar, attr, value, old_value)
        self._raise_if_cancelled()

    def _raise_if_cancelled(self):
        if self.cancel_event.is_set():
            raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
