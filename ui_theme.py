"""Motyw aplikacji: jasny, ciemny albo zgodny z systemem (Windows i macOS)."""
from string import Template
from typing import Dict

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_CHOICES = (
    (THEME_SYSTEM, "Jak w systemie"),
    (THEME_LIGHT, "Jasny"),
    (THEME_DARK, "Ciemny"),
)

DARK: Dict[str, str] = {
    "bg": "#10151d", "surface": "#171f2a", "surface2": "#202b39", "input": "#0f151d",
    "border": "#283343", "border_strong": "#3a4a5f", "text": "#e7edf5", "muted": "#8998ac",
    "accent": "#24b99f", "accent_text": "#53e2c3", "accent_button": "#087f70", "accent_hover": "#099782",
    "on_accent": "#ffffff", "button": "#243041", "button_hover": "#2f3e52",
    "danger_bg": "#35252b", "danger_text": "#ffc2c2", "danger_border": "#70434a",
    "error": "#ff7b7b", "success": "#43e0c1", "warning": "#f2c14e", "warning_bg": "#3a3220", "selection": "#147d72", "disabled": "#6f7d90",
}
LIGHT: Dict[str, str] = {
    "bg": "#f3f5f8", "surface": "#ffffff", "surface2": "#e9eef3", "input": "#ffffff",
    "border": "#d8dee6", "border_strong": "#b8c3cf", "text": "#17202b", "muted": "#5b6878",
    "accent": "#0f9f88", "accent_text": "#0b7d6c", "accent_button": "#0b7d6c", "accent_hover": "#0a6d5e",
    "on_accent": "#ffffff", "button": "#ffffff", "button_hover": "#eef2f6",
    "danger_bg": "#fdf0f0", "danger_text": "#a32d2d", "danger_border": "#efbcbc",
    "error": "#c0392b", "success": "#0b7d6c", "warning": "#9a6a00", "warning_bg": "#fdf3dc", "selection": "#9fe1cb", "disabled": "#9aa5b2",
}

STYLESHEET = Template("""
QMainWindow, QWidget { background: $bg; color: $text; }
QLabel#brand { color: $accent_text; font-size: 17pt; font-weight: 800; }
QLabel#brandTitle { color: $text; font-size: 17pt; font-weight: 700; letter-spacing: 1px; }
QLabel#eyebrow { color: $muted; font-size: 8pt; letter-spacing: 1px; }
QLabel#subtitle, QLabel#muted, QLabel#fileStatus { color: $muted; }
QLabel#fieldError { color: $error; }
QLabel#statusTitle { font-weight: 600; }
QTabWidget::pane { border: 1px solid $border; border-radius: 12px; top: -1px; background: $bg; }
QTabBar::tab { background: $surface; color: $muted; padding: 10px 16px; margin-right: 4px;
               border: 1px solid $border; border-bottom: none;
               border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background: $surface2; color: $accent_text; font-weight: 700; }
QTabBar::tab:hover:!selected { color: $text; }
QGroupBox { background: $surface; border: 1px solid $border; border-radius: 11px;
            margin-top: 12px; padding: 18px 16px 14px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: $text; }
QLabel { background: transparent; }
QLineEdit, QPlainTextEdit, QComboBox { background: $input; color: $text; border: 1px solid $border_strong;
                                       border-radius: 7px; padding: 7px 10px;
                                       selection-background-color: $selection; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid $accent; }
QLineEdit[error="true"] { border: 1px solid $error; }
QLineEdit:disabled, QComboBox:disabled { color: $disabled; }
QPlainTextEdit { font-family: "$mono"; }
QComboBox QAbstractItemView { background: $surface; color: $text; selection-background-color: $selection; }
QPushButton, QToolButton { background: $button; color: $text; border: 1px solid $border_strong;
                           border-radius: 7px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover, QToolButton:hover { background: $button_hover; }
QPushButton:disabled { color: $disabled; }
QPushButton#primary { background: $accent_button; border: 1px solid $accent_button; color: $on_accent;
                      padding: 10px 20px; }
QPushButton#primary:hover { background: $accent_hover; }
QPushButton#primary:disabled { background: $surface2; border-color: $border; color: $disabled; }
QPushButton#danger { color: $danger_text; border-color: $danger_border; background: $danger_bg; }
QPushButton#danger:disabled { color: $disabled; border-color: $border; background: $surface; }
QToolButton#link { background: transparent; border: none; color: $accent_text; padding: 4px 6px; }
QToolButton#link:hover { text-decoration: underline; }
QPushButton#helpButton { padding: 0; border-radius: 15px; font-weight: 800; color: $accent_text; }
QRadioButton { spacing: 8px; padding: 4px 8px; background: transparent; }
QCheckBox { spacing: 8px; padding: 4px 2px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;
                       border: 2px solid $border_strong; background: $input; }
QCheckBox::indicator:checked { border-color: $accent; background: $accent; }
QCheckBox::indicator:disabled { background: $surface2; border-color: $border; }
QRadioButton::indicator { width: 16px; height: 16px; border-radius: 9px;
                          border: 2px solid $border_strong; background: $input; }
QRadioButton::indicator:checked { border-color: $accent; background: $accent; }
QToolTip { background: $surface2; color: $text; border: 1px solid $accent; padding: 6px 8px; }
QTextBrowser { background: $input; border: 1px solid $border; border-radius: 10px; padding: 14px; }
QProgressBar { background: $surface2; border: none; border-radius: 4px; height: 8px;
               text-align: center; color: transparent; }
QProgressBar::chunk { background: $accent; border-radius: 4px; }
QFrame#sidebar { background: $surface; border: none; border-right: 1px solid $border; }
QFrame#sidebar QLabel { background: transparent; }
QLabel#navSection { color: $muted; font-size: 8pt; letter-spacing: 1px; padding: 10px 12px 2px; }
QLabel#navBrand { color: $accent_text; font-size: 13pt; font-weight: 800; padding: 4px 12px 0; }
QLabel#navBrandTitle { color: $text; font-size: 9pt; font-weight: 700; letter-spacing: 1px; padding: 0 12px 8px; }
QPushButton#navItem { text-align: left; background: transparent; border: none; border-radius: 8px;
                      padding: 9px 12px; font-weight: 600; color: $text; }
QPushButton#navItem:hover { background: $button_hover; }
QPushButton#navItem:checked { background: $surface2; color: $accent_text; }
QLabel#pageTitle { font-size: 15pt; font-weight: 700; }
QTableWidget { background: $input; color: $text; border: 1px solid $border; border-radius: 8px;
               gridline-color: $border; selection-background-color: $selection; selection-color: $text; }
QHeaderView::section { background: $surface2; color: $muted; border: none; border-bottom: 1px solid $border;
                       padding: 6px 8px; font-weight: 600; }
QTableCornerButton::section { background: $surface2; border: none; }
QDateEdit { background: $input; color: $text; border: 1px solid $border_strong; border-radius: 7px; padding: 6px 10px; }
QLabel#warningNote { background: $warning_bg; color: $warning; border-radius: 7px; padding: 8px 10px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $border_strong; min-height: 24px; border-radius: 4px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: $border_strong; min-width: 24px; border-radius: 4px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
""")


def system_prefers_dark(app) -> bool:
    """Czy system (Windows/macOS) używa ciemnego motywu. Qt 6.5+: styleHints().colorScheme()."""
    from PySide6.QtCore import Qt

    hints = app.styleHints()
    if hasattr(hints, "colorScheme"):
        scheme = hints.colorScheme()
        if scheme != Qt.ColorScheme.Unknown:
            return scheme == Qt.ColorScheme.Dark
    window_color = app.palette().window().color()
    return window_color.lightness() < 128


def resolve_palette(app, mode: str) -> Dict[str, str]:
    if mode == THEME_LIGHT:
        return LIGHT
    if mode == THEME_DARK:
        return DARK
    return DARK if system_prefers_dark(app) else LIGHT


def build_stylesheet(palette: Dict[str, str], mono_family: str) -> str:
    return STYLESHEET.substitute(palette, mono=mono_family)


def monospace_family() -> str:
    from PySide6.QtGui import QFontDatabase

    return QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
