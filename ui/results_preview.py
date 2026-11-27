"""Podgląd odczytanych wyników: tabela torów pod edytorem, aktualizowana na bieżąco."""
from typing import Dict

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

COLUMNS = (("Tor", None), ("Czas [s]", "czas"), ("Miejsce", "miejsce"), ("%", "procent"), ("HF", "hf"), ("Pkt", "punkty"))


def _track_key(track: str):
    return (0, int(track)) if str(track).isdigit() else (1, str(track))


class ResultsPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel("")
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([title for title, _ in COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMinimumHeight(140)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)

    def show_results(self, results: Dict[str, dict], summary: str) -> None:
        self.summary.setText(summary)
        self.table.setRowCount(len(results))
        for row, track in enumerate(sorted(results, key=_track_key)):
            data = results[track]
            for column, (_, key) in enumerate(COLUMNS):
                if key is None:
                    value = str(track)
                elif key == "czas":
                    value = f"{data['czas']:.2f}"
                else:
                    value = str(data.get(key) or "—")
                self.table.setItem(row, column, QTableWidgetItem(value))
