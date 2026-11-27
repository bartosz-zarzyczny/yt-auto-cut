"""Formularz opisu zawodów: nazwa, data z kalendarza, miejsce, typ i poziom — zamiast ręcznej edycji pliku."""
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate, QTimer, Signal
from PySide6.QtWidgets import QDateEdit, QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

SAVE_DELAY_MS = 600


class CompetitionForm(QWidget):
    """Emituje `changed(dict)` chwilę po edycji (słownik zgodny z generate_names.apply_match_fields)."""

    changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Liga ZSD — runda 4")
        self.match_date = QDateEdit()
        self.match_date.setCalendarPopup(True)
        self.match_date.setDisplayFormat("yyyy-MM-dd")
        self.match_date.setDate(QDate.currentDate())
        self.location = QLineEdit()
        self.location.setPlaceholderText("Strzelnica Pasternik, Kraków")
        self.match_type = QLineEdit()
        self.match_type.setPlaceholderText("Zawody, Trening, Liga")
        self.level = QLineEdit()
        self.level.setPlaceholderText("I, II, III")
        form.addRow("Nazwa zawodów", self.name)
        form.addRow("Data", self.match_date)
        form.addRow("Miejsce", self.location)
        form.addRow("Typ zawodów", self.match_type)
        form.addRow("Poziom", self.level)
        layout.addLayout(form)

        self.title_preview = QLabel("")
        self.title_preview.setObjectName("muted")
        self.title_preview.setWordWrap(True)
        layout.addWidget(self.title_preview)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SAVE_DELAY_MS)
        self._timer.timeout.connect(self._emit_changed)
        self._loading = False
        for field in (self.name, self.location, self.match_type, self.level):
            field.textEdited.connect(self._schedule)
        self.match_date.dateChanged.connect(self._schedule)

    def set_data(self, name: str = "", match_date: Optional[date] = None, location: str = "",
                 match_type: str = "", level: str = "") -> None:
        """Wypełnia pola bez wysyłania sygnału zmiany."""
        self._loading = True
        try:
            self.name.setText(name)
            if match_date is not None:
                self.match_date.setDate(QDate(match_date.year, match_date.month, match_date.day))
            self.location.setText(location)
            self.match_type.setText(match_type)
            self.level.setText(level)
        finally:
            self._loading = False

    def data(self) -> dict:
        selected = self.match_date.date()
        return {
            "name": self.name.text().strip(),
            "match_date": date(selected.year(), selected.month(), selected.day()),
            "location": self.location.text().strip(),
            "match_type": self.match_type.text().strip(),
            "level": self.level.text().strip(),
        }

    def set_title_preview(self, text: str) -> None:
        self.title_preview.setText(text)

    def flush(self) -> None:
        """Natychmiast zgłasza oczekującą zmianę (np. przed montażem)."""
        if self._timer.isActive():
            self._timer.stop()
            self._emit_changed()

    def _schedule(self, *_):
        if not self._loading:
            self._timer.start()

    def _emit_changed(self):
        self.changed.emit(self.data())
