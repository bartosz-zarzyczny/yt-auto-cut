"""Pasek boczny z krokami pracy (zamiast zakładek u góry) i stos stron."""
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

STATUS_OK = "ok"
STATUS_WARNING = "warning"

# Ikona i rola koloru dla statusu kroku (None = zwykła ikona kroku).
STATUS_ICONS = {STATUS_OK: ("circle_check", "success"), STATUS_WARNING: ("alert", "warning")}

IconFactory = Callable[[str, str], object]


class StepNavigation(QWidget):
    """Pasek boczny + strony. Interfejs zgodny z QTabWidget w zakresie, którego używa okno
    (addTab, setCurrentWidget, setCurrentIndex, currentIndex, currentWidget, widget, indexOf, count)."""

    currentChanged = Signal(int)

    def __init__(self, icon_factory: IconFactory, parent=None):
        super().__init__(parent)
        self._icon_factory = icon_factory
        self._buttons: List[QPushButton] = []
        self._icons: List[str] = []
        self._statuses: Dict[int, Optional[str]] = {}
        self._tooltips: Dict[int, str] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(210)
        self._sidebar_layout = QVBoxLayout(self.sidebar)
        self._sidebar_layout.setContentsMargins(10, 16, 10, 14)
        self._sidebar_layout.setSpacing(2)
        brand = QLabel("IPSC")
        brand.setObjectName("navBrand")
        title = QLabel("VIDEO AUTOMATO")
        title.setObjectName("navBrandTitle")
        self._sidebar_layout.addWidget(brand)
        self._sidebar_layout.addWidget(title)
        self._top_items = QVBoxLayout()
        self._top_items.setSpacing(2)
        self._bottom_items = QVBoxLayout()
        self._bottom_items.setSpacing(2)
        self._sidebar_layout.addLayout(self._top_items)
        self._sidebar_layout.addStretch(1)
        self._sidebar_layout.addLayout(self._bottom_items)

        self.stack = QStackedWidget()
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idClicked.connect(self.setCurrentIndex)

    # --- budowanie ---
    def add_section(self, title: str, bottom: bool = False) -> None:
        label = QLabel(title.upper())
        label.setObjectName("navSection")
        (self._bottom_items if bottom else self._top_items).addWidget(label)

    def addTab(self, widget: QWidget, label: str, icon_name: str = "list", bottom: bool = False) -> int:
        index = self.stack.addWidget(widget)
        button = QPushButton(label)
        button.setObjectName("navItem")
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        self._group.addButton(button, index)
        self._buttons.append(button)
        self._icons.append(icon_name)
        (self._bottom_items if bottom else self._top_items).addWidget(button)
        self._refresh_icon(index)
        if index == 0:
            button.setChecked(True)
        return index

    # --- zgodność z QTabWidget ---
    def count(self) -> int:
        return self.stack.count()

    def widget(self, index: int) -> QWidget:
        return self.stack.widget(index)

    def indexOf(self, widget: QWidget) -> int:
        return self.stack.indexOf(widget)

    def currentIndex(self) -> int:
        return self.stack.currentIndex()

    def currentWidget(self) -> QWidget:
        return self.stack.currentWidget()

    def setCurrentIndex(self, index: int) -> None:
        if not 0 <= index < self.count():
            return
        self._buttons[index].setChecked(True)
        if self.stack.currentIndex() != index:
            self.stack.setCurrentIndex(index)
            self.currentChanged.emit(index)

    def setCurrentWidget(self, widget: QWidget) -> None:
        self.setCurrentIndex(self.indexOf(widget))

    # --- statusy kroków ---
    def set_status(self, index: int, status: Optional[str], tooltip: str = "") -> None:
        self._statuses[index] = status
        self._tooltips[index] = tooltip
        self._buttons[index].setToolTip(tooltip)
        self._refresh_icon(index)

    def status(self, index: int) -> Optional[str]:
        return self._statuses.get(index)

    def refresh_icons(self) -> None:
        for index in range(len(self._buttons)):
            self._refresh_icon(index)

    def _refresh_icon(self, index: int) -> None:
        name, role = STATUS_ICONS.get(self._statuses.get(index), (self._icons[index], "text"))
        self._buttons[index].setIcon(self._icon_factory(name, role))
