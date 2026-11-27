"""Proste ikony konturowe (SVG) w kolorze motywu — wyglądają tak samo na Windows i macOS (zamiast emoji)."""
from functools import lru_cache

ICON_PATHS = {
    "play": '<path d="M7 4v16l13-8z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "scissors": '<circle cx="6" cy="7" r="3"/><circle cx="6" cy="17" r="3"/>'
                '<path d="M8.6 8.6L20 18"/><path d="M8.6 15.4L20 6"/>',
    "upload": '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 17v3h16v-3"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "save": '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4"/><rect x="8" y="13" width="8" height="5"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/>'
            '<path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "external": '<path d="M14 4h6v6"/><path d="M20 4l-9 9"/>'
                '<path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>',
    "film": '<rect x="3" y="4" width="18" height="16" rx="2"/>'
            '<path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
    "check": '<path d="M5 12l5 5L20 7"/>',
}

SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)
RENDER_SIZE = 64


def svg_markup(name: str, color: str) -> str:
    return SVG_TEMPLATE.format(color=color, body=ICON_PATHS[name])


@lru_cache(maxsize=128)
def icon(name: str, color: str):
    """QIcon z ikony konturowej w podanym kolorze (wymaga istniejącej QApplication)."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg_markup(name, color).encode("utf-8")))
    pixmap = QPixmap(RENDER_SIZE, RENDER_SIZE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
