"""Tabela planu montażu: plik → tor → H/V → wynik → start timera → co się stanie.

Numer toru i orientację zmienia się w tabeli (lub przyciskami W górę / W dół) zamiast w mapowanie_torow.txt."""
from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

COL_FILE, COL_TRACK, COL_ORIENTATION, COL_TIME, COL_TIMER, COL_ACTION = range(6)
HEADERS = ("Plik", "Tor", "H/V", "Czas", "Start timera", "Co się stanie")
ORIENTATION_DEFAULT = ""

TIMER_NOT_CHECKED = "not_checked"
TIMER_NOT_FOUND = "not_found"


@dataclass
class PlanRow:
    file_name: str
    track: str
    orientation: str          # "" = domyślna, "H" lub "V" = wpisana w mapowanie_torow.txt
    run_time: Optional[float]
    timer: object             # float (sekundy), TIMER_NOT_CHECKED albo TIMER_NOT_FOUND
    action: str               # "render", "skip_no_result", "skip_exists"
    output_name: str


ACTION_TEXT = {
    "render": "Montaż → {output}",
    "skip_no_result": "Pominięty: brak wyniku dla toru",
    "skip_exists": "Pominięty: gotowy film już istnieje",
}


class PlanTable(QWidget):
    mapping_changed = Signal(list)      # [(tor, orientacja), ...] w kolejności wierszy
    refresh_requested = Signal()
    detect_timer_requested = Signal()

    def __init__(self, icon_factory, parent=None):
        super().__init__(parent)
        self._icon_factory = icon_factory
        self._rows: List[PlanRow] = []
        self._default_orientation = "V"
        self._colors: Dict[str, str] = {}
        self._populating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        tools = QHBoxLayout()
        self.summary = QLabel("Plan pojawi się po wskazaniu folderu z nagraniami.")
        self.summary.setObjectName("muted")
        self.up_button = QPushButton("W górę")
        self.down_button = QPushButton("W dół")
        self.refresh_button = QPushButton("Odśwież")
        self.timer_button = QPushButton("Wykryj start timera")
        self.timer_button.setToolTip("Analizuje dźwięk nagrań (może potrwać), aby pokazać, gdzie zacznie się film.")
        for button in (self.up_button, self.down_button):
            button.setToolTip("Zamienia numer toru z sąsiednim nagraniem.")
        tools.addWidget(self.summary, 1)
        for button in (self.up_button, self.down_button, self.refresh_button, self.timer_button):
            tools.addWidget(button)
        layout.addLayout(tools)

        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                                   | QAbstractItemView.SelectedClicked)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_FILE, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_ACTION, QHeaderView.Stretch)
        for column in (COL_TRACK, COL_ORIENTATION, COL_TIME, COL_TIMER):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.setMinimumHeight(200)
        layout.addWidget(self.table, 1)

        self.table.itemChanged.connect(self._on_item_changed)
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.timer_button.clicked.connect(self.detect_timer_requested.emit)
        self.refresh_icons()

    # --- wygląd ---
    def set_colors(self, colors: Dict[str, str]) -> None:
        self._colors = colors
        self.refresh_icons()
        if self._rows:
            self.set_rows(self._rows, self._default_orientation)

    def refresh_icons(self) -> None:
        for button, name in ((self.up_button, "arrow_up"), (self.down_button, "arrow_down"),
                             (self.refresh_button, "refresh"), (self.timer_button, "wave")):
            button.setIcon(self._icon_factory(name, "text"))

    def set_detecting(self, running: bool) -> None:
        self.timer_button.setText("Przerwij analizę" if running else "Wykryj start timera")
        for button in (self.up_button, self.down_button, self.refresh_button):
            button.setEnabled(not running)

    def show_message(self, text: str) -> None:
        self._rows = []
        self.table.setRowCount(0)
        self.summary.setText(text)

    # --- dane ---
    def rows(self) -> List[PlanRow]:
        return list(self._rows)

    def set_rows(self, rows: List[PlanRow], default_orientation: str) -> None:
        """Wiersze są pokazywane w kolejności torów; zaznaczenie podąża za plikiem."""
        current = self.table.currentRow()
        selected_file = self._rows[current].file_name if 0 <= current < len(self._rows) else None
        self._rows = sorted(rows, key=lambda row: (int(row.track) if row.track.isdigit() else 10**6, row.file_name))
        rows = self._rows
        self._default_orientation = default_orientation
        self._populating = True
        try:
            self.table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                self._fill_row(index, row)
        finally:
            self._populating = False
        for index, row in enumerate(rows):
            if row.file_name == selected_file:
                self.table.selectRow(index)
                break
        render = sum(1 for row in rows if row.action == "render")
        skipped = len(rows) - render
        no_timer = sum(1 for row in rows if row.action == "render" and row.timer == TIMER_NOT_FOUND)
        parts = [f"Do montażu: {render} z {len(rows)}"]
        if skipped:
            parts.append(f"pominięte: {skipped}")
        if no_timer:
            parts.append(f"bez wykrytego timera: {no_timer} (zostaną w całości)")
        self.summary.setText(" · ".join(parts))

    def _item(self, text: str, editable: bool = False, role: Optional[str] = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if editable:
            flags |= Qt.ItemIsEditable
        item.setFlags(flags)
        if role and role in self._colors:
            item.setForeground(QBrush(QColor(self._colors[role])))
        return item

    def _fill_row(self, index: int, row: PlanRow) -> None:
        skipped = row.action != "render"
        muted = "muted" if skipped else None
        self.table.setItem(index, COL_FILE, self._item(row.file_name, role=muted))
        track = self._item(row.track, editable=True)
        track.setToolTip("Kliknij dwukrotnie, aby zmienić numer toru.")
        self.table.setItem(index, COL_TRACK, track)

        combo = QComboBox()
        combo.addItem(f"Domyślna ({self._default_orientation})", ORIENTATION_DEFAULT)
        combo.addItem("Pionowe (V)", "V")
        combo.addItem("Poziome (H)", "H")
        combo.setCurrentIndex(max(0, combo.findData(row.orientation)))
        combo.currentIndexChanged.connect(lambda _i, r=index: self._on_orientation_changed(r))
        self.table.setCellWidget(index, COL_ORIENTATION, combo)

        time_text = f"{row.run_time:.2f} s" if row.run_time is not None else "—"
        self.table.setItem(index, COL_TIME, self._item(time_text, role=muted))
        if row.timer == TIMER_NOT_CHECKED or skipped:
            timer_text, timer_role = "nie sprawdzono" if not skipped else "—", "muted"
        elif row.timer == TIMER_NOT_FOUND:
            timer_text, timer_role = "nie wykryto · cały film", "warning"
        else:
            timer_text, timer_role = f"{row.timer:.2f} s", "success"
        self.table.setItem(index, COL_TIMER, self._item(timer_text, role=timer_role))
        action_text = ACTION_TEXT.get(row.action, row.action).format(output=row.output_name)
        action = self._item(action_text, role="warning" if skipped else None)
        action.setToolTip(row.output_name)
        self.table.setItem(index, COL_ACTION, action)

    # --- edycja ---
    def mapping(self) -> List[tuple]:
        """(tor, orientacja) w kolejności nazw plików — tak jak czyta je mapowanie_torow.txt."""
        return [(row.track, row.orientation) for row in sorted(self._rows, key=lambda row: row.file_name)]

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._populating or item.column() != COL_TRACK:
            return
        text = item.text().strip()
        row = self._rows[item.row()]
        if not text.isdigit() or int(text) < 1:
            self._populating = True
            item.setText(row.track)
            self._populating = False
            return
        row.track = str(int(text))
        self.mapping_changed.emit(self.mapping())

    def _on_orientation_changed(self, index: int) -> None:
        if self._populating or index >= len(self._rows):
            return
        combo = self.table.cellWidget(index, COL_ORIENTATION)
        self._rows[index].orientation = combo.currentData()
        self.mapping_changed.emit(self.mapping())

    def _move_selected(self, step: int) -> None:
        index = self.table.currentRow()
        other = index + step
        if index < 0 or not 0 <= other < len(self._rows):
            return
        self._rows[index].track, self._rows[other].track = self._rows[other].track, self._rows[index].track
        moved = self._rows[index].file_name
        self.set_rows(self._rows, self._default_orientation)
        for row_index, row in enumerate(self._rows):
            if row.file_name == moved:
                self.table.selectRow(row_index)
        self.mapping_changed.emit(self.mapping())
