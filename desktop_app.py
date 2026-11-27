import re
import sys
import time
from pathlib import Path

try:
    import PySide6.QtWidgets  # noqa: F401
except ImportError:
    from system_check import show_report_without_qt
    show_report_without_qt()
    sys.exit(1)

from datetime import time as dt_time
from functools import partial
from threading import Event
from typing import Dict, Optional
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSystemTrayIcon,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from dataclasses import dataclass
from file_migration import fix_path, move_old_files
from app_settings import (
    CLOUDFLARE_KEYS,
    KEY_BUFFER_API,
    KEY_CLOUDFLARE_ACCESS_KEY_ID,
    KEY_CLOUDFLARE_ENDPOINT,
    KEY_CLOUDFLARE_PUBLIC_URL,
    KEY_CLOUDFLARE_SECRET_ACCESS_KEY,
    SETTINGS_FILE,
    ensure_settings_file,
    load_settings,
    save_settings,
    saved_buffer_api_key,
    saved_cloudflare_settings,
)
from system_check import format_html, run_system_check
from ui_icons import icon
from ui_theme import (
    THEME_CHOICES,
    THEME_SYSTEM,
    build_stylesheet,
    monospace_family,
    resolve_palette,
)

PROJECT_DIR = Path(__file__).resolve().parent
WEEKDAY_NAMES = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]
PUBLISH_TIMES = [f"{g:02d}:{m:02d}" for g in range(24) for m in range(0, 60, 15)]
SOCIAL_LINKS = (
    ("GitHub", "https://github.com/bartosz-zarzyczny"),
    ("YouTube", "https://www.youtube.com/@Mr_BartekZ"),
    ("Instagram", "https://www.instagram.com/mr_bartekz/"),
    ("Facebook", "https://www.facebook.com/profile.php?id=61587533125970"),
    ("X", "https://x.com/Mr_BartekZ"),
)
PROGRESS_STEPS = 1000  # rozdzielczość paska postępu montażu
AUTOSAVE_DELAY_MS = 800  # zapis edytora po tej przerwie w pisaniu
move_old_files(PROJECT_DIR)
ensure_settings_file()

try:
    from ipsc_automato import (
        FOLDER_MUZYKI,
        FOLDER_WEJSCIOWY,
        FOLDER_WYJSCIOWY,
        PLIK_OPISU_ZAWODOW,
        PLIK_Z_TEKSTAMI,
        PLIK_Z_TORAMI,
        PLIK_Z_WYNIKAMI,
        TRYB_WYNIKOW_ECM,
        TRYB_WYNIKOW_PRACTISCORE,
        TRYB_WYNIKOW_TRENING,
        KonfiguracjaSciezek,
        uruchom_automatyzacje,
    )
    ASSEMBLY_ERROR = ""
except Exception as import_error:
    # Brak biblioteki/programu nie może uniemożliwić uruchomienia okna z zakładką Pomoc.
    ASSEMBLY_ERROR = f"{type(import_error).__name__}: {import_error}"
    FOLDER_WEJSCIOWY = str(PROJECT_DIR / "Surowe")
    FOLDER_WYJSCIOWY = str(PROJECT_DIR / "Gotowe")
    FOLDER_MUZYKI = str(PROJECT_DIR / "Muzyka")
    PLIK_Z_WYNIKAMI = str(PROJECT_DIR / "wyniki.txt")
    PLIK_Z_TEKSTAMI = str(PROJECT_DIR / "teksty_wideo.txt")
    PLIK_Z_TORAMI = str(PROJECT_DIR / "mapowanie_torow.txt")
    PLIK_OPISU_ZAWODOW = str(PROJECT_DIR / "opis_zawodow.txt")
    TRYB_WYNIKOW_PRACTISCORE = "practiscore"
    TRYB_WYNIKOW_ECM = "ecm"
    TRYB_WYNIKOW_TRENING = "trening"
    uruchom_automatyzacje = None

    @dataclass(frozen=True)
    class KonfiguracjaSciezek:
        folder_wejsciowy: Path = Path(FOLDER_WEJSCIOWY)
        folder_wyjsciowy: Path = Path(FOLDER_WYJSCIOWY)
        folder_muzyki: Path = Path(FOLDER_MUZYKI)
        plik_z_wynikami: Path = Path(PLIK_Z_WYNIKAMI)
        plik_z_tekstami: Path = Path(PLIK_Z_TEKSTAMI)
        plik_z_torami: Path = Path(PLIK_Z_TORAMI)
        plik_opisu_zawodow: Path = Path(PLIK_OPISU_ZAWODOW)
        domyslna_orientacja: str = "V"
        dodaj_napisy: bool = True
        plik_logo: str = ""
        tryb_wynikow: str = TRYB_WYNIKOW_PRACTISCORE
        add_video_texts: bool = True
        add_music: bool = True
        trim_only: bool = False
        overwrite_existing: bool = False


BUFFER_VIDEO_LIST_PATH = str(PROJECT_DIR / "buffer.txt")
RESULTS_MODES = (
    (TRYB_WYNIKOW_PRACTISCORE, "Practiscore"),
    (TRYB_WYNIKOW_ECM, "ECM"),
    (TRYB_WYNIKOW_TRENING, "Trening"),
)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds} s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


class AssemblyWorker(QObject):
    log = Signal(str)
    progress = Signal(int, int, str, str)
    render_progress = Signal(float)
    completed = Signal(bool, str)

    def __init__(self, config: KonfiguracjaSciezek, cancel_event: Event):
        super().__init__()
        self.config = config
        self.cancel_event = cancel_event
        self.error_count = 0
        self.completed_count = 0
        self.skipped_count = 0

    def run(self):
        try:
            success = uruchom_automatyzacje(
                konfiguracja=self.config,
                log_callback=self.log.emit,
                progress_callback=self._report_progress,
                cancel_event=self.cancel_event,
                render_progress_callback=self.render_progress.emit,
            )
        except Exception as error:
            self.log.emit(f"BŁĄD: {error}")
            self.completed.emit(False, str(error))
            return

        if not success and self.cancel_event.is_set():
            self.completed.emit(False, "Generowanie przerwano przez użytkownika.")
        elif self.skipped_count and not self.completed_count and not self.error_count:
            self.completed.emit(
                False,
                "Wszystkie nagrania pominięto: sprawdź, czy wyniki zawierają przypisane tory.",
            )
        elif not success or self.error_count:
            self.completed.emit(
                False,
                "Montaż nie powiódł się. Sprawdź log i wymagania systemowe."
                if not self.error_count
                else f"Montaż zakończony z błędami ({self.error_count} filmów). Sprawdź log.",
            )
        else:
            self.completed.emit(True, "Montaż zakończony.")

    def _report_progress(self, index: int, total: int, name: str, status: str):
        if status == "error":
            self.error_count += 1
        elif status in ("done", "exists"):
            self.completed_count += 1
        elif status == "skipped":
            self.skipped_count += 1
        self.progress.emit(index, total, name, status)


class YouTubeWorker(QObject):
    log = Signal(str)
    completed = Signal(bool, str)

    def __init__(
        self,
        folder: Path,
        description_file: Path,
        publish: bool,
        cancel_event: Event,
        schedule: Optional[Dict[int, dt_time]] = None,
        publish_now: bool = False,
        also_unlisted: bool = False,
    ):
        super().__init__()
        self.also_unlisted = also_unlisted
        self.folder = folder
        self.description_file = description_file
        self.publish = publish
        self.cancel_event = cancel_event
        self.schedule = schedule
        self.publish_now = publish_now

    def run(self):
        try:
            import youtube_upload

            videos = sorted(
                (p for p in self.folder.iterdir() if p.suffix.lower() == ".mp4"),
                key=lambda p: p.name.casefold(),
            )
            if not videos:
                self.completed.emit(False, f"Brak plików MP4 w folderze: {self.folder}")
                return
            self.log.emit(f"[YT] Znaleziono filmów: {len(videos)}")
            youtube_upload.upload_videos(
                videos,
                self.publish,
                description_file=self.description_file,
                log=self.log.emit,
                cancel_event=self.cancel_event,
                hours=self.schedule,
                immediate=self.publish_now,
                also_unlisted=self.also_unlisted,
            )
        except Exception as error:
            if type(error).__name__ == "UploadCancelled":
                self.completed.emit(False, "Wysyłanie przerwano przez użytkownika.")
            else:
                self.log.emit(f"[YT] BŁĄD: {error}")
                self.completed.emit(False, f"Wysyłanie nie powiodło się: {error}")
            return
        self.completed.emit(True, "Wysyłanie zakończone." if self.publish else "Podgląd zakończony.")


class BufferWorker(QObject):
    log = Signal(str)
    completed = Signal(bool, str)

    def __init__(
        self,
        token: str,
        links: list,
        platforms: list,
        descriptions: Dict[str, str],
        hours: Optional[Dict[int, dt_time]],
        post_types: Dict[str, str],
        cancel_event: Event,
    ):
        super().__init__()
        self.token = token
        self.links = links
        self.platforms = platforms
        self.descriptions = descriptions
        self.hours = hours
        self.post_types = post_types
        self.cancel_event = cancel_event

    def run(self):
        try:
            import buffer_upload

            created, skipped = buffer_upload.send_drafts(
                self.token,
                self.links,
                self.platforms,
                self.descriptions,
                self.hours,
                self.log.emit,
                is_cancelled=self.cancel_event.is_set,
                post_types=self.post_types,
            )
        except Exception as error:
            self.log.emit(f"[Buffer] BŁĄD: {error}")
            self.completed.emit(False, f"Tworzenie szkiców nie powiodło się: {error}")
            return
        if self.cancel_event.is_set():
            self.completed.emit(False, "Tworzenie szkiców przerwano przez użytkownika.")
            return
        self.completed.emit(True, f"Gotowe. Utworzono szkiców: {created}, pominięto: {skipped}.")


class CloudflareWorker(QObject):
    log = Signal(str)
    uploaded = Signal(str)
    completed = Signal(bool, str)

    def __init__(self, values: dict, folder: Path, list_path: Path, cancel_event: Event):
        super().__init__()
        self.values = values
        self.folder = folder
        self.list_path = list_path
        self.cancel_event = cancel_event

    def run(self):
        try:
            import cloudflare_upload

            config = cloudflare_upload.build_config(self.values)
            sent, existing, failed = cloudflare_upload.upload_folder(
                config,
                self.folder,
                self.list_path,
                self.log.emit,
                self.uploaded.emit,
                is_cancelled=self.cancel_event.is_set,
            )
        except Exception as error:
            self.log.emit(f"[Cloudflare] BŁĄD: {error}")
            self.completed.emit(False, f"Wysyłanie do Cloudflare nie powiodło się: {error}")
            return
        if self.cancel_event.is_set():
            self.completed.emit(False, "Wysyłanie do Cloudflare przerwano przez użytkownika.")
            return
        message = f"Gotowe. Wysłano: {sent}, już istniały: {existing}, błędy: {failed}."
        self.completed.emit(failed == 0, message)


class SystemCheckWorker(QObject):
    finished = Signal(str, bool)

    def run(self):
        try:
            results = run_system_check()
            self.finished.emit(format_html(results), any(not w.ok for w in results))
        except Exception as error:
            self.finished.emit(f"<p style='color:#ff7b7b'>Test systemu nie powiódł się: {error}</p>", True)


class MainWindow(QMainWindow):
    PATHS = (
        ("folder_wejsciowy", "Nagrania źródłowe", "dir"),
        ("folder_wyjsciowy", "Gotowe filmy", "dir"),
        ("folder_muzyki", "Muzyka", "dir"),
        ("plik_logo", "Logo", "image"),
        ("plik_z_wynikami", "Wyniki zawodów", "file"),
        ("plik_z_torami", "Mapowanie torów", "file"),
        ("plik_z_tekstami", "Teksty wideo", "file"),
        ("plik_opisu_zawodow", "Opis zawodów", "file"),
    )
    SUBTITLE_PATH_KEYS = ("plik_z_wynikami",)
    EDITORS = (
        ("plik_z_tekstami", "Teksty wideo"),
        ("plik_opisu_zawodow", "Opis zawodów"),
        ("plik_z_torami", "Mapowanie torów"),
        ("plik_z_wynikami", "Wyniki zawodów"),
        ("buffer_video_list", "Lista filmów Buffer"),
    )

    def __init__(self):
        super().__init__()
        self.settings = QSettings("YTAutoCut", "Desktop")
        self.fields: Dict[str, QLineEdit] = {}
        self.editors: Dict[str, QPlainTextEdit] = {}
        self.editor_status: Dict[str, QLabel] = {}
        self._dirty_editors = set()
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[AssemblyWorker] = None
        self.cancel_event: Optional[Event] = None
        self.yt_thread: Optional[QThread] = None
        self.yt_worker: Optional[YouTubeWorker] = None
        self.yt_cancel_event: Optional[Event] = None
        self.buffer_thread: Optional[QThread] = None
        self.buffer_worker: Optional[BufferWorker] = None
        self.buffer_cancel_event: Optional[Event] = None
        self.cloudflare_thread: Optional[QThread] = None
        self.cloudflare_worker: Optional[CloudflareWorker] = None
        self.cloudflare_cancel_event: Optional[Event] = None
        self.job_complete = False
        self.test_thread: Optional[QThread] = None
        self.test_worker: Optional[SystemCheckWorker] = None
        self._test_automatic = False
        self._icon_widgets = []
        self._autosave_timers: Dict[str, QTimer] = {}
        self._path_errors: Dict[str, QLabel] = {}
        self._render_started_at: Optional[float] = None
        self._current_video = (0, 0, "")
        self.theme_mode = str(self.settings.value("theme", THEME_SYSTEM))
        app = QApplication.instance()
        self.colors = resolve_palette(app, self.theme_mode)
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.setWindowTitle("IPSC Video Automato")
        self.resize(1120, 850)
        self.setMinimumSize(860, 680)
        self._build_ui()
        self._load_settings()
        self._load_startup_files()
        self._install_shortcuts()
        if hasattr(app.styleHints(), "colorSchemeChanged"):
            app.styleHints().colorSchemeChanged.connect(self._on_system_theme_changed)

    def _build_ui(self):
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 26, 30, 28)
        layout.setSpacing(18)

        header = QHBoxLayout()
        logo = QLabel("IPSC")
        logo.setObjectName("brand")
        name = QLabel("VIDEO AUTOMATO")
        name.setObjectName("brandTitle")
        header.addWidget(logo)
        header.addWidget(name)
        header.addStretch(1)
        version = QLabel("WORKSPACE  /  2026")
        version.setObjectName("eyebrow")
        header.addWidget(version)
        layout.addLayout(header)

        description = QLabel("Produkcja i organizacja materiałów wideo z zawodów")
        description.setObjectName("subtitle")
        layout.addWidget(description)

        self.tabs = QTabWidget()
        self.tab_main = self._build_main_tab()
        self.tab_competition = self._build_competition_tab()
        self.tab_config = self._build_config_tab()
        self.tabs.addTab(self.tab_main, "  Główna  ")
        self.tabs.addTab(self.tab_competition, "  Zawody  ")
        self.tabs.addTab(self.tab_config, "  Konfiguracja  ")
        self.tabs.addTab(self._build_youtube_tab(), "  YouTube  ")
        self.tab_buffer = self._build_buffer_tab()
        self.tabs.addTab(self.tab_buffer, "  Buffer  ")
        self.tab_help = self._build_help_tab()
        self.tabs.addTab(self.tab_help, "  Pomoc  ")
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self._apply_theme()

    def _build_main_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        paths = QGroupBox("Projekt wideo")
        paths_layout = QVBoxLayout(paths)
        paths_layout.setSpacing(12)
        self._add_path_field(paths_layout, "folder_wejsciowy", "Nagrania źródłowe", "dir")
        self._add_path_field(paths_layout, "folder_wyjsciowy", "Gotowe filmy", "dir")
        self.subtitles_check = QCheckBox("Czy dodać wyniki")
        self.subtitles_check.setToolTip(
            "Steruje tylko planszą z wynikami na dole filmu."
        )
        self.subtitles_check.setChecked(
            str(self.settings.value("dodaj_napisy", "false")).lower() == "true"
        )
        self.subtitles_check.toggled.connect(self._remember_subtitles)
        layout.addWidget(paths)
        layout.addWidget(self._build_assembly_mode())

        bar = QHBoxLayout()
        status_column = QVBoxLayout()
        status_column.setSpacing(2)
        self.status = QLabel("Gotowy do pracy")
        self.status.setObjectName("statusTitle")
        self.status_detail = QLabel("Wybierz nagrania i kliknij przycisk, aby zacząć.")
        self.status_detail.setObjectName("muted")
        status_column.addWidget(self.status)
        status_column.addWidget(self.status_detail)
        self.start_button = QPushButton(self.start_button_text)
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(42)
        self.start_button.setToolTip("Skrót: Ctrl+Enter (na Macu ⌘+Enter)")
        self.start_button.clicked.connect(self._start)
        self._set_icon(self.start_button, "scissors" if self.mode_trim_only.isChecked() else "play", "on_accent")
        self.cancel_button = QPushButton("Przerwij")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setMinimumHeight(42)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self._set_icon(self.cancel_button, "stop", "danger_text")
        bar.addLayout(status_column, 1)
        bar.addWidget(self.start_button)
        bar.addWidget(self.cancel_button)
        layout.addLayout(bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, PROGRESS_STEPS)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        log_bar = QHBoxLayout()
        self.log_toggle = QToolButton()
        self.log_toggle.setCheckable(True)
        self.log_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.log_toggle.toggled.connect(self._toggle_log)
        self._set_icon(self.log_toggle, "list")
        copy_log = QToolButton()
        copy_log.setText("Kopiuj dziennik")
        copy_log.setToolTip("Kopiuje cały dziennik do schowka — przydatne przy zgłaszaniu problemu.")
        copy_log.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        copy_log.clicked.connect(self._copy_log)
        self._set_icon(copy_log, "copy")
        log_bar.addWidget(self.log_toggle)
        log_bar.addWidget(copy_log)
        log_bar.addStretch(1)
        layout.addLayout(log_bar)

        self.log_group = QGroupBox("Dziennik pracy")
        log_layout = QVBoxLayout(self.log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Tutaj pojawią się postęp montażu i komunikaty aplikacji.")
        log_layout.addWidget(self.log_view)
        layout.addWidget(self.log_group, 1)
        self.log_spacer = QWidget()
        layout.addWidget(self.log_spacer, 1)
        self.log_toggle.setChecked(str(self.settings.value("log_visible", "false")).lower() == "true")
        self._toggle_log(self.log_toggle.isChecked())
        return page

    def _toggle_log(self, visible: bool):
        self.log_group.setVisible(visible)
        self.log_spacer.setVisible(not visible)
        self.log_toggle.setText("Ukryj dziennik" if visible else "Pokaż dziennik")
        self.settings.setValue("log_visible", "true" if visible else "false")

    def _copy_log(self, checked: bool = False):
        del checked
        QGuiApplication.clipboard().setText(self.log_view.toPlainText())
        self.status_detail.setText("Dziennik skopiowano do schowka.")

    # --- motyw i ikony ---
    def _set_icon(self, widget, name: str, role: str = "text"):
        self._icon_widgets.append((widget, name, role))
        widget.setIcon(icon(name, self.colors[role]))

    def _apply_theme(self):
        app = QApplication.instance()
        self.colors = resolve_palette(app, self.theme_mode)
        app.setStyleSheet(build_stylesheet(self.colors, monospace_family()))
        for widget, name, role in self._icon_widgets:
            widget.setIcon(icon(name, self.colors[role]))
        if hasattr(self, "help_browser"):
            self._render_help()

    def _on_system_theme_changed(self, *_):
        if self.theme_mode == THEME_SYSTEM:
            self._apply_theme()

    def _set_theme_mode(self, mode: str):
        self.theme_mode = mode
        self.settings.setValue("theme", mode)
        self._apply_theme()

    def _install_shortcuts(self):
        # Qt zamienia Ctrl na ⌘ na macOS.
        for sequence in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(sequence), self, activated=self._start_from_shortcut)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self._save_all_editors)

    def _start_from_shortcut(self):
        if self.start_button.isEnabled():
            self.tabs.setCurrentWidget(self.tab_main)
            self._start()

    def _save_all_editors(self):
        for key, _ in self.EDITORS:
            self._autosave(key)
        self.status_detail.setText("Zapisano wszystkie pliki.")

    def _build_assembly_mode(self):
        group = QGroupBox("Rodzaj montażu")
        layout = QVBoxLayout(group)
        modes = QHBoxLayout()
        self.mode_full = QRadioButton("Pełny montaż")
        self.mode_full.setToolTip("Przycięcie, muzyka, wyniki, teksty wideo, logo i zmiana rozdzielczości.")
        self.mode_trim_only = QRadioButton("Tylko przycięcie")
        self.mode_trim_only.setToolTip(
            "Szybko: film przycięty do przebiegu, bez muzyki, napisów i logo. "
            "Obraz nie jest kodowany ponownie, więc start może wypaść ułamek sekundy wcześniej."
        )
        mode_group = QButtonGroup(self)
        mode_group.addButton(self.mode_full)
        mode_group.addButton(self.mode_trim_only)
        trim_only = str(self.settings.value("trim_only", "false")).lower() == "true"
        (self.mode_trim_only if trim_only else self.mode_full).setChecked(True)
        modes.addWidget(self.mode_full)
        modes.addWidget(self.mode_trim_only)
        modes.addStretch(1)
        layout.addLayout(modes)

        options = QHBoxLayout()
        self.music_check = QCheckBox("Dodaj muzykę")
        self.music_check.setChecked(str(self.settings.value("add_music", "true")).lower() == "true")
        self.music_check.toggled.connect(
            lambda checked: self.settings.setValue("add_music", "true" if checked else "false")
        )
        self.overwrite_check = QCheckBox("Nadpisuj gotowe filmy")
        self.overwrite_check.setToolTip(
            "Odznaczone: nagrania, które mają już gotowy film w folderze wyjściowym, są pomijane."
        )
        self.overwrite_check.setChecked(
            str(self.settings.value("overwrite_existing", "false")).lower() == "true"
        )
        self.overwrite_check.toggled.connect(
            lambda checked: self.settings.setValue("overwrite_existing", "true" if checked else "false")
        )
        options.addWidget(self.subtitles_check)
        options.addWidget(self.music_check)
        options.addWidget(self.overwrite_check)
        options.addStretch(1)
        layout.addLayout(options)

        hint = QLabel("Montaż niczego nie publikuje. Sprawdź filmy, a potem wyślij je w zakładkach YouTube i Buffer.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.mode_trim_only.toggled.connect(self._on_assembly_mode_changed)
        self._on_assembly_mode_changed()
        return group

    def _on_assembly_mode_changed(self, *_):
        trim_only = self.mode_trim_only.isChecked()
        self.settings.setValue("trim_only", "true" if trim_only else "false")
        self.subtitles_check.setEnabled(not trim_only)
        self.music_check.setEnabled(not trim_only)
        self.start_button_text = "Rozpocznij przycinanie" if trim_only else "Rozpocznij montaż"
        if hasattr(self, "start_button"):
            self.start_button.setText(self.start_button_text)
            self._icon_widgets = [entry for entry in self._icon_widgets if entry[0] is not self.start_button]
            self._set_icon(self.start_button, "scissors" if trim_only else "play", "on_accent")

    def _build_config_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        description = QLabel("Folder z podkładami oraz treści wykorzystywane przy generowaniu filmów.")
        description.setObjectName("muted")
        layout.addWidget(description)

        music = QGroupBox("Biblioteka muzyki")
        music_layout = QVBoxLayout(music)
        self._add_path_field(music_layout, "folder_muzyki", "Folder z muzyką", "dir")
        layout.addWidget(music)
        logo = QGroupBox("Logo na filmie")
        logo_layout = QVBoxLayout(logo)
        self._add_path_field(logo_layout, "plik_logo", "Plik logo", "image")
        logo_hint = QLabel(
            "Logo pojawi się w prawym górnym rogu (maks. 200×200 px, proporcje zachowane). "
            "Puste pole = bez logo."
        )
        logo_hint.setObjectName("muted")
        logo_hint.setWordWrap(True)
        logo_layout.addWidget(logo_hint)
        layout.addWidget(logo)
        video_texts_editor = self._create_editor("plik_z_tekstami", "Teksty wideo")
        self.video_texts_check = QCheckBox("Czy dodać teksty wideo")
        self.video_texts_check.setChecked(
            str(self.settings.value("add_video_texts", "true")).lower() == "true"
        )
        self.video_texts_check.toggled.connect(self._remember_video_texts)
        video_texts_editor.layout().insertWidget(0, self.video_texts_check)
        layout.addWidget(video_texts_editor)
        layout.addWidget(self._create_editor("plik_opisu_zawodow", "Opis zawodów"))
        layout.addWidget(self._build_api_keys())
        layout.addWidget(self._build_appearance())
        layout.addStretch(1)
        page.setObjectName("scrollPage")
        page.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        page.setStyleSheet("QWidget#scrollPage { background: transparent; }")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _build_appearance(self):
        group = QGroupBox("Wygląd")
        row = QHBoxLayout(group)
        label = QLabel("Motyw")
        label.setMinimumWidth(150)
        self.theme_combo = QComboBox()
        for mode, title in THEME_CHOICES:
            self.theme_combo.addItem(title, mode)
        index = self.theme_combo.findData(self.theme_mode)
        self.theme_combo.setCurrentIndex(max(index, 0))
        self.theme_combo.currentIndexChanged.connect(
            lambda _index: self._set_theme_mode(self.theme_combo.currentData())
        )
        row.addWidget(label)
        row.addWidget(self.theme_combo)
        row.addStretch(1)
        return group

    API_FIELDS = (
        (KEY_BUFFER_API, "Buffer API", False, "Token z developers.buffer.com"),
        (KEY_CLOUDFLARE_ENDPOINT, "Cloudflare: endpoint S3", False,
         "https://<ID_KONTA>.r2.cloudflarestorage.com/<bucket>"),
        (KEY_CLOUDFLARE_ACCESS_KEY_ID, "Cloudflare: Access Key ID", False, ""),
        (KEY_CLOUDFLARE_SECRET_ACCESS_KEY, "Cloudflare: Secret Key", True, ""),
        (KEY_CLOUDFLARE_PUBLIC_URL, "Cloudflare: adres publiczny", False, "https://pub-xxxx.r2.dev"),
    )

    def _build_api_keys(self):
        group = QGroupBox("Klucze usług (Buffer, Cloudflare)")
        layout = QVBoxLayout(group)
        hint = QLabel(f"Wartości są zapisywane w pliku {SETTINGS_FILE.name} w folderze programu.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        stored = load_settings()
        self.api_fields: Dict[str, QLineEdit] = {}
        for key, title, secret, placeholder in self.API_FIELDS:
            row = QHBoxLayout()
            label = QLabel(title)
            label.setMinimumWidth(200)
            field = QLineEdit(str(stored.get(key) or ""))
            field.setPlaceholderText(placeholder)
            field.setClearButtonEnabled(True)
            if secret:
                field.setEchoMode(QLineEdit.PasswordEchoOnEdit)
            field.editingFinished.connect(self._save_api_keys)
            self.api_fields[key] = field
            row.addWidget(label)
            row.addWidget(field, 1)
            layout.addLayout(row)
        self.api_status = QLabel("")
        self.api_status.setObjectName("fileStatus")
        layout.addWidget(self.api_status)
        return group

    def _save_api_keys(self):
        settings = load_settings()
        changed = False
        for key, field in self.api_fields.items():
            value = field.text().strip()
            if str(settings.get(key) or "") != value:
                settings[key] = value
                changed = True
        if not changed:
            return
        try:
            save_settings(settings)
        except OSError as error:
            self.api_status.setText(f"Nie udało się zapisać {SETTINGS_FILE.name}: {error}")
            return
        self.api_status.setText(f"Zapisano w {SETTINGS_FILE.name} ({time.strftime('%H:%M')}).")

    def _build_youtube_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        description = QLabel("Wysyłanie gotowych filmów (Shorts) na YouTube z planowaniem publikacji.")
        description.setObjectName("muted")
        layout.addWidget(description)
        layout.addWidget(self._build_publish_section())

        group = QGroupBox("Folder z filmami do wysłania")
        group_layout = QVBoxLayout(group)
        self.yt_same_folder = QCheckBox("Taki sam jak „Gotowe filmy” (zakładka Główna)")
        self.yt_same_folder.setChecked(
            str(self.settings.value("yt_ten_sam_folder", "true")).lower() == "true"
        )
        self.yt_same_folder.toggled.connect(self._on_yt_folder_mode_changed)
        group_layout.addWidget(self.yt_same_folder)
        row = QHBoxLayout()
        label = QLabel("Folder YouTube")
        label.setMinimumWidth(150)
        self.yt_folder = QLineEdit(str(self.settings.value("folder_youtube", "")))
        self.yt_folder.setPlaceholderText("Wskaż folder z plikami MP4…")
        self.yt_folder.editingFinished.connect(
            lambda: self.settings.setValue("folder_youtube", self.yt_folder.text().strip())
        )
        self.yt_browse_button = QPushButton("Przeglądaj…")
        self._set_icon(self.yt_browse_button, "folder")
        self.yt_browse_button.clicked.connect(self._choose_yt_folder)
        row.addWidget(label)
        row.addWidget(self.yt_folder, 1)
        row.addWidget(self.yt_browse_button)
        group_layout.addLayout(row)
        layout.addWidget(group)

        self.yt_preview_only = QCheckBox("Tylko podgląd (pokaż tytuły i terminy, bez wysyłania)")
        layout.addWidget(self.yt_preview_only)
        self.yt_also_unlisted = QCheckBox(
            "Dodatkowo opublikuj prywatnie (tylko z linkiem, natychmiast) jako osobny film"
        )
        layout.addWidget(self.yt_also_unlisted)

        bar = QHBoxLayout()
        self.yt_status = QLabel("Gotowy do wysyłania")
        self.yt_status.setObjectName("muted")
        self.yt_start = QPushButton("Wyślij do YouTube")
        self.yt_start.setObjectName("primary")
        self._set_icon(self.yt_start, "upload", "on_accent")
        self.yt_start.setMinimumHeight(44)
        self.yt_start.clicked.connect(self._send_to_yt)
        self.yt_cancel = QPushButton("Przerwij wysyłanie")
        self.yt_cancel.setObjectName("danger")
        self._set_icon(self.yt_cancel, "stop", "danger_text")
        self.yt_cancel.setMinimumHeight(44)
        self.yt_cancel.setEnabled(False)
        self.yt_cancel.clicked.connect(self._cancel_yt)
        bar.addWidget(self.yt_status, 1)
        bar.addWidget(self.yt_start)
        bar.addWidget(self.yt_cancel)
        layout.addLayout(bar)

        log_group = QGroupBox("Dziennik wysyłania")
        log_layout = QVBoxLayout(log_group)
        self.yt_log = QPlainTextEdit()
        self.yt_log.setReadOnly(True)
        self.yt_log.setPlaceholderText("Tutaj pojawią się komunikaty z wysyłania na YouTube.")
        log_layout.addWidget(self.yt_log)
        layout.addWidget(log_group, 1)

        self.fields["folder_wyjsciowy"].textChanged.connect(self._refresh_yt_folder)
        self._on_yt_folder_mode_changed()
        self.yt_log.setMinimumHeight(140)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        page.setObjectName("scrollPage")
        page.setStyleSheet("QWidget#scrollPage { background: transparent; }")
        return scroll

    def _build_buffer_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        description = QLabel("Tworzenie szkiców postów w Buffer (bez publikacji).")
        description.setObjectName("muted")
        layout.addWidget(description)

        platforms = QGroupBox("Platformy")
        platforms_layout = QHBoxLayout(platforms)
        self.buffer_facebook = QCheckBox("Facebook")
        self.buffer_instagram = QCheckBox("Instagram")
        self.buffer_x = QCheckBox("X/Twitter")
        self.buffer_facebook_type = self._create_buffer_post_type_combo(self.buffer_facebook)
        self.buffer_instagram_type = self._create_buffer_post_type_combo(self.buffer_instagram)
        for checkbox, post_type in (
            (self.buffer_facebook, self.buffer_facebook_type),
            (self.buffer_instagram, self.buffer_instagram_type),
        ):
            column = QVBoxLayout()
            column.addWidget(checkbox)
            column.addWidget(post_type)
            platforms_layout.addLayout(column)
        platforms_layout.addWidget(self.buffer_x)
        platforms_layout.addStretch(1)
        layout.addWidget(platforms)

        self.buffer_facebook_text = self._create_post_description(
            "Opis na Facebook", "Treść opisu dla Facebooka…", max_chars=None, max_hashtags=None, layout=layout
        )
        self.buffer_instagram_text = self._create_post_description(
            "Opis na Instagram", "Treść opisu dla Instagrama…", max_chars=None, max_hashtags=5, layout=layout
        )
        self.buffer_x_text = self._create_post_description(
            "Opis na X/Twitter", "Treść opisu dla X/Twitter…", max_chars=280, max_hashtags=None, layout=layout
        )

        layout.addWidget(self._create_editor("buffer_video_list", "Lista filmów Buffer"))
        layout.addWidget(self._build_cloudflare_group())

        layout.addWidget(self._build_buffer_schedule())

        bar = QHBoxLayout()
        self.buffer_status = QLabel("Gotowe do utworzenia szkiców")
        self.buffer_status.setObjectName("muted")
        self.buffer_send = QPushButton("Utwórz szkice w Buffer")
        self.buffer_send.setObjectName("primary")
        self._set_icon(self.buffer_send, "upload", "on_accent")
        self.buffer_send.setMinimumHeight(44)
        self.buffer_send.clicked.connect(self._send_to_buffer)
        self.buffer_cancel = QPushButton("Przerwij")
        self.buffer_cancel.setObjectName("danger")
        self._set_icon(self.buffer_cancel, "stop", "danger_text")
        self.buffer_cancel.setMinimumHeight(44)
        self.buffer_cancel.setEnabled(False)
        self.buffer_cancel.clicked.connect(self._cancel_buffer)
        bar.addWidget(self.buffer_status, 1)
        bar.addWidget(self.buffer_send)
        bar.addWidget(self.buffer_cancel)
        layout.addLayout(bar)

        self.buffer_log = QPlainTextEdit()
        self.buffer_log.setReadOnly(True)
        self.buffer_log.setPlaceholderText("Tutaj pojawią się komunikaty z tworzenia szkiców w Buffer.")
        self.buffer_log.setMinimumHeight(140)
        layout.addWidget(self.buffer_log)
        layout.addStretch(1)

        page.setObjectName("scrollPage")
        page.setStyleSheet("QWidget#scrollPage { background: transparent; }")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _create_post_description(
        self, title: str, placeholder: str, max_chars: Optional[int], max_hashtags: Optional[int], layout
    ) -> QPlainTextEdit:
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        editor = QPlainTextEdit()
        editor.setPlaceholderText(placeholder)
        editor.setMinimumHeight(80)
        counter = QLabel()
        counter.setObjectName("muted")
        counter.setWordWrap(True)
        group_layout.addWidget(editor)
        group_layout.addWidget(counter)

        def update_counter():
            text = editor.toPlainText()
            parts = [f"Znaki: {len(text)}" + (f"/{max_chars}" if max_chars else "")]
            over_limit = bool(max_chars and len(text) > max_chars)
            if max_hashtags is not None:
                hashtags = len(re.findall(r"#\w+", text))
                parts.append(f"hashtagi: {hashtags}/{max_hashtags}")
                over_limit = over_limit or hashtags > max_hashtags
            if over_limit:
                parts.append("przekroczono limit")
            counter.setText(" · ".join(parts))
            counter.setObjectName("fieldError" if over_limit else "muted")
            counter.style().unpolish(counter)
            counter.style().polish(counter)

        editor.textChanged.connect(update_counter)
        update_counter()
        layout.addWidget(group)
        return editor

    def _build_day_grid(self, prefix: str):
        """Siatka dni tygodnia z godzinami; klucze ustawień mają postać `{prefix}_dzien_N` i `{prefix}_godzina_N`."""
        defaults = {d: "07:30" if d < 5 else "10:00" for d in range(7)}
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 6, 0, 6)
        days: Dict[int, tuple] = {}
        for index, name in enumerate(WEEKDAY_NAMES):
            checkbox = QCheckBox(name)
            checkbox.setMinimumHeight(30)
            checkbox.setChecked(str(self.settings.value(f"{prefix}_dzien_{index}", "true")).lower() == "true")
            time_combo = QComboBox()
            time_combo.addItems(PUBLISH_TIMES)
            remembered = str(self.settings.value(f"{prefix}_godzina_{index}", defaults[index]))
            if remembered not in PUBLISH_TIMES:
                remembered = defaults[index]
            time_combo.setCurrentText(remembered)
            time_combo.setMaxVisibleItems(12)
            hint = time_combo.sizeHint()
            time_combo.setMinimumSize(int(hint.width() * 1.2), max(34, int(hint.height() * 1.2)))
            checkbox.toggled.connect(time_combo.setEnabled)
            time_combo.setEnabled(checkbox.isChecked())
            grid.addWidget(checkbox, 0, index)
            grid.addWidget(time_combo, 1, index)
            grid.setColumnStretch(index, 1)
            days[index] = (checkbox, time_combo)
        return grid, days

    @staticmethod
    def _connect_day_grid(days: Dict[int, tuple], on_change):
        for checkbox, time_combo in days.values():
            checkbox.toggled.connect(on_change)
            time_combo.currentTextChanged.connect(on_change)

    def _save_day_grid(self, prefix: str, days: Dict[int, tuple]):
        for index, (checkbox, time_combo) in days.items():
            self.settings.setValue(f"{prefix}_dzien_{index}", "true" if checkbox.isChecked() else "false")
            self.settings.setValue(f"{prefix}_godzina_{index}", time_combo.currentText())

    @staticmethod
    def _set_day_grid_active(days: Dict[int, tuple], active: bool):
        for checkbox, time_combo in days.values():
            checkbox.setEnabled(active)
            time_combo.setEnabled(active and checkbox.isChecked())

    @staticmethod
    def _selected_hours(days: Dict[int, tuple]) -> Dict[int, dt_time]:
        return {
            index: dt_time.fromisoformat(time_combo.currentText())
            for index, (checkbox, time_combo) in days.items()
            if checkbox.isChecked()
        }

    def _build_buffer_schedule(self):
        group = QGroupBox("PLANOWANIE SZKICÓW")
        layout = QVBoxLayout(group)
        self.buffer_custom_schedule = QCheckBox("Własne dni i godziny (inaczej: pn–pt 7:30, sob–nd 10:00)")
        self.buffer_custom_schedule.setChecked(str(self.settings.value("buffer_wlasny_plan", "false")).lower() == "true")
        layout.addWidget(self.buffer_custom_schedule)
        grid, self.buffer_days = self._build_day_grid("buffer")
        layout.addLayout(grid)
        self._connect_day_grid(self.buffer_days, self._on_buffer_schedule_changed)
        self.buffer_custom_schedule.toggled.connect(self._on_buffer_schedule_changed)
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._refresh_buffer_schedule()
        return group

    def _on_buffer_schedule_changed(self, *_):
        self.settings.setValue("buffer_wlasny_plan", "true" if self.buffer_custom_schedule.isChecked() else "false")
        self._save_day_grid("buffer", self.buffer_days)
        self._refresh_buffer_schedule()

    def _refresh_buffer_schedule(self):
        self._set_day_grid_active(self.buffer_days, self.buffer_custom_schedule.isChecked())

    def _buffer_hours(self) -> Optional[Dict[int, dt_time]]:
        if not self.buffer_custom_schedule.isChecked():
            return None
        return self._selected_hours(self.buffer_days)

    def _on_yt_folder_mode_changed(self, checked: bool = False):
        del checked
        shared = self.yt_same_folder.isChecked()
        self.settings.setValue("yt_ten_sam_folder", "true" if shared else "false")
        self.yt_folder.setEnabled(not shared)
        self.yt_browse_button.setEnabled(not shared)
        self._refresh_yt_folder()

    def _refresh_yt_folder(self, *_):
        if self.yt_same_folder.isChecked():
            self.yt_folder.setText(self.fields["folder_wyjsciowy"].text().strip())

    def _build_publish_section(self):
        group = QGroupBox("PUBLIKACJA")
        layout = QVBoxLayout(group)
        self.yt_mode_schedule = QRadioButton("Zaplanuj publikację")
        self.yt_mode_publish_now = QRadioButton("Publikuj wszystkie od razu")
        publish_now = str(self.settings.value("yt_od_razu", "false")).lower() == "true"
        self.yt_mode_publish_now.setChecked(publish_now)
        self.yt_mode_schedule.setChecked(not publish_now)
        radio_group = QButtonGroup(self)
        radio_group.addButton(self.yt_mode_schedule)
        radio_group.addButton(self.yt_mode_publish_now)
        layout.addWidget(self.yt_mode_schedule)

        self.yt_custom_schedule = QCheckBox("Własne dni i godziny publikacji (inaczej: pn–pt 7:30, sob–nd 10:00)")
        self.yt_custom_schedule.setChecked(str(self.settings.value("yt_wlasny_plan", "false")).lower() == "true")
        layout.addWidget(self.yt_custom_schedule)

        grid, self.yt_days = self._build_day_grid("yt")
        layout.addLayout(grid)
        layout.addWidget(self.yt_mode_publish_now)
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        for control in (self.yt_mode_schedule, self.yt_mode_publish_now, self.yt_custom_schedule):
            control.toggled.connect(self._on_publish_settings_changed)
        self._connect_day_grid(self.yt_days, self._on_publish_settings_changed)
        self._refresh_publish_controls()
        return group

    def _on_publish_settings_changed(self, *_):
        s = self.settings
        s.setValue("yt_od_razu", "true" if self.yt_mode_publish_now.isChecked() else "false")
        s.setValue("yt_wlasny_plan", "true" if self.yt_custom_schedule.isChecked() else "false")
        self._save_day_grid("yt", self.yt_days)
        self._refresh_publish_controls()

    def _refresh_publish_controls(self):
        schedule = self.yt_mode_schedule.isChecked()
        self.yt_custom_schedule.setEnabled(schedule)
        active = schedule and self.yt_custom_schedule.isChecked()
        self._set_day_grid_active(self.yt_days, active)

    def _publish_times(self) -> Optional[Dict[int, dt_time]]:
        if self.yt_mode_publish_now.isChecked() or not self.yt_custom_schedule.isChecked():
            return None
        return self._selected_hours(self.yt_days)

    def _choose_yt_folder(self, checked: bool = False):
        del checked
        start = self.yt_folder.text().strip() or str(PROJECT_DIR)
        chosen = QFileDialog.getExistingDirectory(self, "Folder z filmami do wysłania", start)
        if chosen:
            self.yt_folder.setText(chosen)
            self.settings.setValue("folder_youtube", chosen)

    def _resolve_yt_folder(self) -> Path:
        field = self.fields["folder_wyjsciowy"] if self.yt_same_folder.isChecked() else self.yt_folder
        return Path(field.text().strip())

    def _send_to_yt(self, checked: bool = False):
        del checked
        folder = self._resolve_yt_folder()
        if not folder.is_dir():
            QMessageBox.warning(self, "Nieprawidłowy folder", f"Folder nie istnieje:\n{folder}")
            return
        publish = not self.yt_preview_only.isChecked()
        publish_times = self._publish_times()
        publish_now = self.yt_mode_publish_now.isChecked()
        if publish_times is not None and not publish_times:
            QMessageBox.warning(self, "Publikacja", "Zaznacz co najmniej jeden dzień tygodnia.")
            return
        mode_description = (
            "NATYCHMIAST jako publiczne" if publish_now else "prywatne, z zaplanowaną publikacją"
        )
        if publish and QMessageBox.question(
            self,
            "Wysyłanie na YouTube",
            f"Wysłać filmy MP4 z folderu:\n{folder}\n\nna YouTube ({mode_description})?",
        ) != QMessageBox.Yes:
            return
        self.yt_log.clear()
        self.yt_status.setText("Wysyłanie…" if publish else "Sprawdzanie (podgląd)…")
        self.yt_start.setEnabled(False)
        self.yt_cancel.setEnabled(True)
        self.yt_cancel_event = Event()
        self.yt_thread = QThread(self)
        self.yt_worker = YouTubeWorker(
            folder,
            Path(self.fields["plik_opisu_zawodow"].text().strip()),
            publish,
            self.yt_cancel_event,
            publish_times,
            publish_now,
            self.yt_also_unlisted.isChecked(),
        )
        self.yt_worker.moveToThread(self.yt_thread)
        self.yt_thread.started.connect(self.yt_worker.run)
        self.yt_worker.log.connect(self.yt_log.appendPlainText)
        self.yt_worker.completed.connect(self._finish_yt)
        self.yt_worker.completed.connect(self.yt_thread.quit)
        self.yt_worker.completed.connect(self.yt_worker.deleteLater)
        self.yt_thread.finished.connect(self.yt_thread.deleteLater)
        self.yt_thread.finished.connect(self._cleanup_yt)
        self.yt_thread.start()

    def _cancel_yt(self, checked: bool = False):
        del checked
        if self.yt_cancel_event is None or self.yt_cancel_event.is_set():
            return
        self.yt_cancel_event.set()
        self.yt_cancel.setEnabled(False)
        self.yt_status.setText("Przerywanie wysyłania…")
        self.yt_log.appendPlainText("Żądanie przerwania wysłane. Wysyłanie zatrzyma się po bieżącym fragmencie pliku.")

    def _finish_yt(self, success: bool, message: str):
        self.yt_status.setText(message)
        self.yt_cancel.setEnabled(False)
        self.yt_cancel_event = None
        if success:
            self.yt_log.appendPlainText(message)
        elif "przerwano" in message.lower():
            self.yt_log.appendPlainText(message)
        else:
            QMessageBox.warning(self, "YouTube", message)

    def _cleanup_yt(self):
        self.yt_worker = None
        self.yt_thread = None
        self.yt_start.setEnabled(True)

    def _create_buffer_post_type_combo(self, checkbox: QCheckBox) -> QComboBox:
        from buffer_upload import DEFAULT_POST_TYPE, POST_TYPES

        combo = QComboBox()
        combo.addItems(list(POST_TYPES))
        combo.setCurrentText(DEFAULT_POST_TYPE)
        combo.setEnabled(checkbox.isChecked())
        checkbox.toggled.connect(combo.setEnabled)
        return combo

    def _buffer_platforms(self) -> list:
        checkboxes = (
            ("facebook", self.buffer_facebook),
            ("instagram", self.buffer_instagram),
            ("x", self.buffer_x),
        )
        return [key for key, checkbox in checkboxes if checkbox.isChecked()]

    def _buffer_post_types(self) -> Dict[str, str]:
        return {
            "facebook": self.buffer_facebook_type.currentText(),
            "instagram": self.buffer_instagram_type.currentText(),
        }

    def _buffer_descriptions(self) -> Dict[str, str]:
        return {
            "facebook": self.buffer_facebook_text.toPlainText().strip(),
            "instagram": self.buffer_instagram_text.toPlainText().strip(),
            "x": self.buffer_x_text.toPlainText().strip(),
        }

    def _send_to_buffer(self, checked: bool = False):
        del checked
        # Importowane leniwie, bo buffer_upload ładuje moduły YouTube.
        from buffer_upload import PLATFORM_LABELS, find_text_problems, parse_video_links

        token = saved_buffer_api_key()
        if not token:
            QMessageBox.warning(self, "Buffer", "Brak klucza Buffer API. Wpisz go w zakładce Konfiguracja → Klucze usług.")
            return
        platforms = self._buffer_platforms()
        if not platforms:
            QMessageBox.warning(self, "Buffer", "Zaznacz co najmniej jedną platformę.")
            return
        links = parse_video_links(self.editors["buffer_video_list"].toPlainText())
        if not links:
            QMessageBox.warning(self, "Buffer", "Lista filmów Buffer nie zawiera żadnych adresów plików wideo.")
            return
        descriptions = self._buffer_descriptions()
        empty = [PLATFORM_LABELS[platform] for platform in platforms if not descriptions[platform]]
        if empty:
            QMessageBox.warning(self, "Buffer", "Uzupełnij opis na: " + ", ".join(empty) + ".")
            return
        problems = find_text_problems(platforms, descriptions)
        if problems:
            QMessageBox.warning(self, "Buffer", "\n".join(problems))
            return
        if self.buffer_custom_schedule.isChecked() and not self._selected_hours(self.buffer_days):
            QMessageBox.warning(self, "Buffer", "Zaznacz co najmniej jeden dzień tygodnia.")
            return
        if QMessageBox.question(
            self,
            "Tworzenie szkiców",
            f"Utworzyć szkice w Buffer dla {len(links)} filmów?\n\nSzkice nie zostaną opublikowane.",
        ) != QMessageBox.Yes:
            return

        self.buffer_log.clear()
        self.buffer_status.setText("Tworzenie szkiców…")
        self.buffer_send.setEnabled(False)
        self.buffer_cancel.setEnabled(True)
        self.buffer_cancel_event = Event()
        self.buffer_thread = QThread(self)
        self.buffer_worker = BufferWorker(
            token,
            links,
            platforms,
            descriptions,
            self._buffer_hours(),
            self._buffer_post_types(),
            self.buffer_cancel_event,
        )
        self.buffer_worker.moveToThread(self.buffer_thread)
        self.buffer_thread.started.connect(self.buffer_worker.run)
        self.buffer_worker.log.connect(self.buffer_log.appendPlainText)
        self.buffer_worker.completed.connect(self._finish_buffer)
        self.buffer_worker.completed.connect(self.buffer_thread.quit)
        self.buffer_worker.completed.connect(self.buffer_worker.deleteLater)
        self.buffer_thread.finished.connect(self.buffer_thread.deleteLater)
        self.buffer_thread.finished.connect(self._cleanup_buffer)
        self.buffer_thread.start()

    def _cancel_buffer(self, checked: bool = False):
        del checked
        if self.buffer_cancel_event is None or self.buffer_cancel_event.is_set():
            return
        self.buffer_cancel_event.set()
        self.buffer_cancel.setEnabled(False)
        self.buffer_status.setText("Przerywanie…")
        self.buffer_log.appendPlainText("Żądanie przerwania wysłane. Zatrzymanie nastąpi po bieżącym szkicu.")

    def _finish_buffer(self, success: bool, message: str):
        self.buffer_status.setText(message)
        self.buffer_cancel.setEnabled(False)
        self.buffer_cancel_event = None
        self.buffer_log.appendPlainText(message)
        if not success and "przerwano" not in message.lower():
            QMessageBox.warning(self, "Buffer", message)

    def _cleanup_buffer(self):
        self.buffer_worker = None
        self.buffer_thread = None
        self.buffer_send.setEnabled(True)

    def _build_cloudflare_group(self) -> QGroupBox:
        group = QGroupBox("Wysyłka filmów do Cloudflare")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        label = QLabel("Folder z filmami")
        label.setMinimumWidth(150)
        self.cloudflare_folder = QLineEdit(str(self.settings.value("folder_cloudflare", FOLDER_WYJSCIOWY)))
        browse_button = QPushButton("Przeglądaj…")
        self._set_icon(browse_button, "folder")
        browse_button.clicked.connect(self._choose_cloudflare_folder)
        row.addWidget(label)
        row.addWidget(self.cloudflare_folder, 1)
        row.addWidget(browse_button)
        layout.addLayout(row)

        bar = QHBoxLayout()
        self.cloudflare_status = QLabel("Gotowe do wysyłki")
        self.cloudflare_status.setObjectName("muted")
        self.cloudflare_send = QPushButton("Wyślij do Cloudflare")
        self._set_icon(self.cloudflare_send, "upload")
        self.cloudflare_send.setMinimumHeight(40)
        self.cloudflare_send.clicked.connect(self._send_to_cloudflare)
        self.cloudflare_cancel = QPushButton("Przerwij")
        self.cloudflare_cancel.setObjectName("danger")
        self._set_icon(self.cloudflare_cancel, "stop", "danger_text")
        self.cloudflare_cancel.setMinimumHeight(40)
        self.cloudflare_cancel.setEnabled(False)
        self.cloudflare_cancel.clicked.connect(self._cancel_cloudflare)
        bar.addWidget(self.cloudflare_status, 1)
        bar.addWidget(self.cloudflare_send)
        bar.addWidget(self.cloudflare_cancel)
        layout.addLayout(bar)

        self.cloudflare_log = QPlainTextEdit()
        self.cloudflare_log.setReadOnly(True)
        self.cloudflare_log.setPlaceholderText("Tutaj pojawią się komunikaty z wysyłki do Cloudflare.")
        self.cloudflare_log.setMinimumHeight(110)
        layout.addWidget(self.cloudflare_log)
        return group

    def _choose_cloudflare_folder(self, checked: bool = False):
        del checked
        start = self.cloudflare_folder.text().strip() or FOLDER_WYJSCIOWY
        chosen = QFileDialog.getExistingDirectory(self, "Folder z filmami do wysłania na Cloudflare", start)
        if chosen:
            self.cloudflare_folder.setText(chosen)
            self.settings.setValue("folder_cloudflare", chosen)

    def _send_to_cloudflare(self, checked: bool = False):
        del checked
        from cloudflare_upload import CloudflareUploadError, build_config

        try:
            config_values = saved_cloudflare_settings()
            build_config(config_values)
        except CloudflareUploadError as error:
            QMessageBox.warning(self, "Cloudflare", str(error))
            return
        folder = Path(self.cloudflare_folder.text().strip())
        if not folder.is_dir():
            QMessageBox.warning(self, "Cloudflare", "Wybrany folder nie istnieje.")
            return
        list_path = Path(self.fields["buffer_video_list"].text().strip())
        if not list_path.name:
            QMessageBox.warning(self, "Cloudflare", "Wskaż plik listy filmów Buffer.")
            return
        self.settings.setValue("folder_cloudflare", str(folder))

        self.cloudflare_log.clear()
        self.cloudflare_status.setText("Wysyłanie do Cloudflare…")
        self.cloudflare_send.setEnabled(False)
        self.cloudflare_cancel.setEnabled(True)
        self.cloudflare_cancel_event = Event()
        self.cloudflare_thread = QThread(self)
        self.cloudflare_worker = CloudflareWorker(
            config_values, folder, list_path, self.cloudflare_cancel_event
        )
        self.cloudflare_worker.moveToThread(self.cloudflare_thread)
        self.cloudflare_thread.started.connect(self.cloudflare_worker.run)
        self.cloudflare_worker.log.connect(self.cloudflare_log.appendPlainText)
        self.cloudflare_worker.uploaded.connect(self._on_cloudflare_link)
        self.cloudflare_worker.completed.connect(self._finish_cloudflare)
        self.cloudflare_worker.completed.connect(self.cloudflare_thread.quit)
        self.cloudflare_worker.completed.connect(self.cloudflare_worker.deleteLater)
        self.cloudflare_thread.finished.connect(self.cloudflare_thread.deleteLater)
        self.cloudflare_thread.finished.connect(self._cleanup_cloudflare)
        self.cloudflare_thread.start()

    def _on_cloudflare_link(self, link: str):
        # Plik listy zapisuje wątek; edytor dopisuje ten sam link bez oznaczania go jako zmienionego.
        editor = self.editors["buffer_video_list"]
        text = editor.toPlainText()
        if link in text.split():
            return
        separator = "" if not text or text.endswith("\n") else "\n"
        editor.blockSignals(True)
        try:
            editor.setPlainText(f"{text}{separator}{link}\n")
        finally:
            editor.blockSignals(False)

    def _cancel_cloudflare(self, checked: bool = False):
        del checked
        if self.cloudflare_cancel_event is None or self.cloudflare_cancel_event.is_set():
            return
        self.cloudflare_cancel_event.set()
        self.cloudflare_cancel.setEnabled(False)
        self.cloudflare_status.setText("Przerywanie…")
        self.cloudflare_log.appendPlainText("Żądanie przerwania wysłane. Zatrzymanie nastąpi po bieżącym pliku.")

    def _finish_cloudflare(self, success: bool, message: str):
        self.cloudflare_status.setText(message)
        self.cloudflare_log.appendPlainText(message)
        if not success and "przerwano" not in message.lower():
            QMessageBox.warning(self, "Cloudflare", message)

    def _cleanup_cloudflare(self):
        self.cloudflare_worker = None
        self.cloudflare_thread = None
        self.cloudflare_cancel_event = None
        self.cloudflare_send.setEnabled(True)
        self.cloudflare_cancel.setEnabled(False)

    def _build_help_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        bar = QHBoxLayout()
        description = QLabel("Sprawdź wymagane biblioteki Pythona, FFmpeg i kodeki wideo.")
        description.setObjectName("muted")
        self.test_button = QPushButton("Test systemu")
        self.test_button.setObjectName("primary")
        self._set_icon(self.test_button, "activity", "on_accent")
        self.test_button.clicked.connect(self._run_system_test)
        bar.addWidget(description, 1)
        bar.addWidget(self.test_button)
        layout.addLayout(bar)

        self.test_results = QTextBrowser()
        self.test_results.setMaximumHeight(320)
        self.test_results.setVisible(False)
        layout.addWidget(self.test_results)

        self.help_browser = QTextBrowser()
        self.help_browser.setOpenExternalLinks(True)
        self._render_help()
        layout.addWidget(self.help_browser, 1)

        about = QHBoxLayout()
        about.setSpacing(4)
        about_label = QLabel("Autor:")
        about_label.setObjectName("muted")
        about.addWidget(about_label)
        for name, url in SOCIAL_LINKS:
            link = QToolButton()
            link.setObjectName("link")
            link.setText(name)
            link.setToolTip(url)
            link.setCursor(Qt.PointingHandCursor)
            link.clicked.connect(lambda _checked=False, target_url=url: QDesktopServices.openUrl(QUrl(target_url)))
            about.addWidget(link)
        about.addStretch(1)
        layout.addLayout(about)
        return page

    def _render_help(self):
        colors = self.colors
        self.help_browser.document().setDefaultStyleSheet(
            f"h1, h2, h3 {{ color: {colors['accent_text']}; }} a {{ color: {colors['accent_text']}; }} "
            f"code, pre {{ background: {colors['surface2']}; }} th, td {{ padding: 4px 8px; }}"
        )
        readme_path = Path(__file__).resolve().parent / "README.md"
        try:
            self.help_browser.setMarkdown(readme_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as error:
            self.help_browser.setPlainText(f"Nie udało się wczytać pliku pomocy:\n{readme_path}\n\n{error}")

    def _run_system_test(self, checked: bool = False, automatic: bool = False):
        del checked
        if self.test_thread is not None:
            return
        self._test_automatic = automatic
        self.test_button.setEnabled(False)
        self.test_button.setText("Trwa testowanie…")
        self.test_results.setVisible(True)
        self.test_results.setHtml("<p>Sprawdzanie systemu, to może potrwać kilka sekund…</p>")
        self.test_thread = QThread(self)
        self.test_worker = SystemCheckWorker()
        self.test_worker.moveToThread(self.test_thread)
        self.test_thread.started.connect(self.test_worker.run)
        self.test_worker.finished.connect(self._show_test_result)
        self.test_worker.finished.connect(self.test_thread.quit)
        self.test_thread.finished.connect(self.test_worker.deleteLater)
        self.test_thread.finished.connect(self.test_thread.deleteLater)
        self.test_thread.finished.connect(self._release_test_thread)
        self.test_thread.start()

    def _release_test_thread(self):
        self.test_thread = None
        self.test_worker = None

    def _test_on_startup(self):
        self._run_system_test(automatic=True)

    def _show_test_result(self, html: str, has_problems: bool):
        if self._test_automatic and not has_problems:
            self.test_results.setVisible(False)
        else:
            self.test_results.setHtml(html)
        self.test_button.setEnabled(True)
        self.test_button.setText("Test systemu")
        if self._test_automatic and has_problems:
            self.tabs.setCurrentWidget(self.tab_help)
            self.status.setText("Wykryto braki w systemie — szczegóły w zakładce Pomoc")

    def _build_competition_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        description = QLabel("Edytuj dane zawodów bezpośrednio w plikach tekstowych używanych przez montaż.")
        description.setObjectName("muted")
        layout.addWidget(description)
        track_mapping = self._create_editor("plik_z_torami", "Mapowanie torów")
        track_mapping.layout().insertLayout(1, self._build_orientation_choice())
        layout.addWidget(track_mapping)
        results = self._create_editor("plik_z_wynikami", "Wyniki zawodów")
        results.layout().insertLayout(0, self._build_results_mode_choice())
        layout.addWidget(results)
        layout.addStretch(1)
        return page

    def _build_results_mode_choice(self):
        row = QHBoxLayout()
        label = QLabel("Format wyników:")
        self.results_mode_group = QButtonGroup(self)
        self.results_mode_buttons: Dict[str, QRadioButton] = {}
        for mode, title in RESULTS_MODES:
            button = QRadioButton(title)
            self.results_mode_group.addButton(button)
            self.results_mode_buttons[mode] = button
            row.addWidget(button)
        remembered = str(self.settings.value("tryb_wynikow", TRYB_WYNIKOW_PRACTISCORE)).lower()
        self.results_mode_buttons.get(remembered, self.results_mode_buttons[TRYB_WYNIKOW_PRACTISCORE]).setChecked(True)
        self.results_mode_group.buttonToggled.connect(self._remember_results_mode)

        row.insertWidget(0, label)
        row.addStretch(1)
        return row

    def _remember_results_mode(self, *_args):
        self.settings.setValue("tryb_wynikow", self._selected_results_mode())

    def _selected_results_mode(self) -> str:
        for mode, button in self.results_mode_buttons.items():
            if button.isChecked():
                return mode
        return TRYB_WYNIKOW_PRACTISCORE

    def _build_orientation_choice(self):
        row = QHBoxLayout()
        label = QLabel("Rodzaj wszystkich filmów:")
        self.radio_vertical = QRadioButton("Wideo Pionowe")
        self.radio_horizontal = QRadioButton("Wideo Poziome")
        group = QButtonGroup(self)
        group.addButton(self.radio_vertical)
        group.addButton(self.radio_horizontal)
        remembered = str(self.settings.value("domyslna_orientacja", "V")).upper()
        (self.radio_horizontal if remembered == "H" else self.radio_vertical).setChecked(True)
        self.radio_vertical.toggled.connect(self._remember_orientation)

        help_button = QPushButton("?")
        help_button.setObjectName("helpButton")
        help_button.setFixedSize(30, 30)
        help_button.setCursor(Qt.PointingHandCursor)
        help_button.setToolTip("Jeżeli chcesz by każdy plik był innego rodzaju przeczytaj pomoc")
        help_button.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_help))

        row.addWidget(label)
        row.addWidget(self.radio_vertical)
        row.addWidget(self.radio_horizontal)
        row.addWidget(help_button)
        row.addStretch(1)
        return row

    def _remember_orientation(self, checked: bool = False):
        del checked
        self.settings.setValue("domyslna_orientacja", self._default_orientation())

    def _remember_subtitles(self, checked: bool = False):
        self.settings.setValue("dodaj_napisy", "true" if checked else "false")

    def _remember_video_texts(self, checked: bool = False):
        self.settings.setValue("add_video_texts", "true" if checked else "false")

    def _default_orientation(self) -> str:
        return "H" if self.radio_horizontal.isChecked() else "V"

    def _add_path_field(self, layout, key: str, label: str, kind: str):
        row = QHBoxLayout()
        label_widget = QLabel(label)
        label_widget.setMinimumWidth(150)
        field = QLineEdit()
        field.setClearButtonEnabled(True)
        field.setPlaceholderText("Wskaż ścieżkę…")
        self.fields[key] = field
        field.editingFinished.connect(partial(self._remember_path, key))
        button = QPushButton("Przeglądaj…")
        self._set_icon(button, "folder")
        button.clicked.connect(partial(self._choose_path, key, kind))
        row.addWidget(label_widget)
        row.addWidget(field, 1)
        row.addWidget(button)
        layout.addLayout(row)
        error = QLabel("")
        error.setObjectName("fieldError")
        error.setWordWrap(True)
        error.setVisible(False)
        self._path_errors[key] = error
        layout.addWidget(error)
        field.textChanged.connect(partial(self._clear_path_error, key))

    def _show_path_error(self, key: str, message: str):
        """Błąd pokazany pod polem (zamiast okienka) i przejście do zakładki z tym polem."""
        field = self.fields[key]
        field.setProperty("error", True)
        field.style().unpolish(field)
        field.style().polish(field)
        label = self._path_errors[key]
        label.setText(message)
        label.setVisible(True)
        for index in range(self.tabs.count()):
            if self.tabs.widget(index).isAncestorOf(field):
                self.tabs.setCurrentIndex(index)
                break
        field.setFocus()
        self.status.setText("Popraw zaznaczone pole")
        self.status_detail.setText(message)

    def _clear_path_error(self, key: str, *_):
        field = self.fields[key]
        if field.property("error"):
            field.setProperty("error", False)
            field.style().unpolish(field)
            field.style().polish(field)
        self._path_errors[key].setVisible(False)

    def _create_editor(self, key: str, title: str):
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        self._add_path_field(layout, key, "Plik TXT", "file")

        editor = QPlainTextEdit()
        editor.setMinimumHeight(125)
        editor.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        editor.setPlaceholderText(f"Wpisz lub wklej treść: {title.lower()}…")
        editor.textChanged.connect(partial(self._mark_dirty, key))
        self.editors[key] = editor
        layout.addWidget(editor, 1)

        controls = QHBoxLayout()
        status = QLabel("Plik nie został jeszcze wczytany")
        status.setObjectName("fileStatus")
        status.setWordWrap(True)
        self.editor_status[key] = status
        layout.addWidget(status)

        controls = QHBoxLayout()
        controls.addStretch(1)
        load_button = QPushButton("Wczytaj ponownie")
        load_button.setToolTip("Wczytuje treść z pliku na dysku. Zmiany w edytorze zapisują się same.")
        self._set_icon(load_button, "refresh")
        load_button.clicked.connect(partial(self._load_file, key, True))
        controls.addWidget(load_button)
        layout.addLayout(controls)

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(AUTOSAVE_DELAY_MS)
        timer.timeout.connect(partial(self._autosave, key))
        self._autosave_timers[key] = timer
        return group

    def _default_paths(self) -> KonfiguracjaSciezek:
        return KonfiguracjaSciezek(
            folder_wejsciowy=Path(FOLDER_WEJSCIOWY),
            folder_wyjsciowy=Path(FOLDER_WYJSCIOWY),
            folder_muzyki=Path(FOLDER_MUZYKI),
            plik_z_wynikami=Path(PLIK_Z_WYNIKAMI),
            plik_z_tekstami=Path(PLIK_Z_TEKSTAMI),
            plik_z_torami=Path(PLIK_Z_TORAMI),
            plik_opisu_zawodow=Path(PLIK_OPISU_ZAWODOW),
        )

    def _load_settings(self):
        defaults = self._default_paths()
        for key in (*(path_key for path_key, _, _ in self.PATHS), "buffer_video_list"):
            default = BUFFER_VIDEO_LIST_PATH if key == "buffer_video_list" else str(getattr(defaults, key))
            value = fix_path(self.settings.value(key, default))
            self.fields[key].setText("" if key == "plik_logo" and value in ("", ".") else str(value))

    def _load_startup_files(self):
        for key, _ in self.EDITORS:
            self._load_file(key, False)

    def _choose_path(self, key: str, kind: str, checked: bool = False):
        del checked
        if key in self.editors and not self._autosave(key):
            return

        current = Path(self.fields[key].text().strip() or ".")
        if kind == "dir":
            path = QFileDialog.getExistingDirectory(self, "Wybierz folder", str(current))
        elif kind == "image":
            path, _ = QFileDialog.getOpenFileName(
                self, "Wybierz logo", str(current),
                "Obrazy (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Wszystkie pliki (*)",
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Wybierz plik tekstowy", str(current), "Pliki tekstowe (*.txt);;Wszystkie pliki (*)"
            )
        if path:
            self.fields[key].setText(path)
            self._remember_path(key)
            if key in self.editors:
                self._load_file(key, True)

    def _remember_path(self, key: str):
        self.settings.setValue(key, self.fields[key].text().strip())

    def _mark_dirty(self, key: str):
        self._dirty_editors.add(key)
        self.editor_status[key].setText("Zapisywanie…")
        timer = self._autosave_timers.get(key)
        if timer is not None:
            timer.start()

    def _autosave(self, key: str) -> bool:
        """Zapisuje edytor, jeśli ma niezapisane zmiany. Zwraca False tylko przy błędzie zapisu."""
        timer = self._autosave_timers.get(key)
        if timer is not None:
            timer.stop()
        if key not in self._dirty_editors:
            return True
        if not self.fields[key].text().strip():
            self.editor_status[key].setText("Wskaż plik, aby zapisać zmiany")
            return False
        return self._save_file(key)

    def _load_file(self, key: str, show_error: bool = True, checked: bool = False):
        del checked
        if key in self._dirty_editors and not self._autosave(key):
            return False

        path = Path(self.fields[key].text().strip())
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            message = f"Nie udało się wczytać pliku:\n{path}\n\n{error}"
            self.editor_status[key].setText("Błąd odczytu pliku")
            if show_error:
                QMessageBox.warning(self, "Błąd odczytu", message)
            else:
                self.editor_status[key].setToolTip(message)
            return False

        editor = self.editors[key]
        editor.blockSignals(True)
        try:
            editor.setPlainText(content)
        finally:
            editor.blockSignals(False)
        self._dirty_editors.discard(key)
        self.editor_status[key].setText(f"Wczytano: {path.name}")
        self.editor_status[key].setToolTip(str(path))
        return True

    def _save_file(self, key: str, show_confirmation: bool = False, checked: bool = False):
        del checked
        path = Path(self.fields[key].text().strip())
        try:
            path.write_text(self.editors[key].toPlainText(), encoding="utf-8")
        except (OSError, UnicodeError) as error:
            message = f"Nie udało się zapisać pliku:\n{path}\n\n{error}"
            self.editor_status[key].setText("Błąd zapisu pliku")
            QMessageBox.warning(self, "Błąd zapisu", message)
            return False

        self._dirty_editors.discard(key)
        self._remember_path(key)
        self.editor_status[key].setText(f"Zapisano automatycznie: {path.name} ({time.strftime('%H:%M:%S')})")
        self.editor_status[key].setToolTip(str(path))
        if show_confirmation:
            self.status.setText(f"Zapisano plik: {path.name}")
        return True

    def _tab_for_editor(self, key: str):
        if key == "buffer_video_list":
            return self.tab_buffer
        if key in {"plik_z_tekstami", "plik_opisu_zawodow"}:
            return self.tab_config
        return self.tab_competition

    def _save_dirty_editors(self):
        for key, _ in self.EDITORS:
            if key in self.SUBTITLE_PATH_KEYS and not self.subtitles_check.isChecked():
                continue
            if not self._autosave(key):
                self.tabs.setCurrentWidget(self._tab_for_editor(key))
                return False
        return True

    def _get_config(self) -> KonfiguracjaSciezek:
        paths = {
            key: (self.fields[key].text().strip() if key == "plik_logo" else Path(self.fields[key].text().strip()))
            for key, _, _ in self.PATHS
        }
        return KonfiguracjaSciezek(
            **paths,
            domyslna_orientacja=self._default_orientation(),
            dodaj_napisy=self.subtitles_check.isChecked(),
            tryb_wynikow=self._selected_results_mode(),
            add_video_texts=self.video_texts_check.isChecked(),
            add_music=self.music_check.isChecked(),
            trim_only=self.mode_trim_only.isChecked(),
            overwrite_existing=self.overwrite_check.isChecked(),
        )

    def _start(self):
        if uruchom_automatyzacje is None:
            QMessageBox.warning(
                self,
                "Brak wymaganych składników",
                "Nie można uruchomić montażu, bo nie załadowano modułu montażu:\n"
                f"{ASSEMBLY_ERROR}\n\nSprawdź zakładkę Pomoc i doinstaluj brakujące elementy.",
            )
            self.tabs.setCurrentWidget(self.tab_help)
            self._run_system_test()
            return
        if not self._save_dirty_editors():
            return
        config = self._get_config()
        for key, label, kind in self.PATHS:
            path = getattr(config, key)
            if key in self.SUBTITLE_PATH_KEYS and (not config.dodaj_napisy or config.trim_only):
                continue
            if key == "plik_z_tekstami" and (not config.add_video_texts or config.trim_only):
                continue
            if key == "folder_muzyki" and (not config.add_music or config.trim_only):
                continue
            if kind == "dir" and not path.is_dir():
                self._show_path_error(key, f"{label}: ten folder nie istnieje.")
                return
            if kind == "file" and not path.is_file():
                self._show_path_error(key, f"{label}: ten plik nie istnieje.")
                return

        try:
            videos = [
                file for file in config.folder_wejsciowy.iterdir()
                if file.suffix.lower() in {".mp4", ".mov"} and "TEMP_MPY_" not in file.name.upper()
            ]
        except OSError as error:
            self._show_path_error("folder_wejsciowy", f"Nie można odczytać nagrań: {error}")
            return
        if not videos:
            self._show_path_error("folder_wejsciowy", "W tym folderze nie ma filmów MP4 ani MOV.")
            return

        for key, _, _ in self.PATHS:
            self.settings.setValue(key, str(getattr(config, key)))
        self.log_view.clear()
        self.status.setText("Przygotowywanie montażu…")
        self.status_detail.setText(f"Nagrania w folderze: {len(videos)}")
        self.progress_bar.setRange(0, PROGRESS_STEPS)
        self.progress_bar.setValue(0)
        self._current_video = (0, len(videos), "")
        self._render_origin = None
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.job_complete = False

        self.cancel_event = Event()
        self.worker_thread = QThread(self)
        self.worker = AssemblyWorker(config, self.cancel_event)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append_log)
        self.worker.progress.connect(self._update_progress)
        self.worker.render_progress.connect(self._update_render_progress)
        self.worker.completed.connect(self._finish)
        self.worker.completed.connect(self.worker_thread.quit)
        self.worker.completed.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._cleanup_thread)
        self.worker_thread.start()

    def _cancel(self):
        if self.cancel_event is None or self.cancel_event.is_set():
            return
        self.cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.status.setText("Przerywanie…")
        self.status_detail.setText("Bieżący etap zostanie bezpiecznie zatrzymany.")
        self._append_log("Żądanie przerwania wysłane. Trwa bezpieczne zatrzymywanie bieżącego etapu.")

    def _append_log(self, text: str):
        self.log_view.appendPlainText(text)

    def _set_overall_progress(self, done_fraction: float):
        self.progress_bar.setValue(int(max(0.0, min(1.0, done_fraction)) * PROGRESS_STEPS))

    def _update_progress(self, index: int, total: int, name: str, status: str):
        labels = {
            "done": "gotowe",
            "error": "błąd",
            "skipped": "pominięto",
            "exists": "już gotowe, pominięto",
            "cancelled": "przerwano",
        }
        if status == "started":
            self._current_video = (index, total, name)
            self._render_origin = None
            self._set_overall_progress((index - 1) / total)
            self.status.setText(f"Film {index} z {total}: {name}")
            self.status_detail.setText("Analiza dźwięku i przycinanie…")
            return
        self._set_overall_progress(index / total)
        self.status.setText(f"Film {index} z {total}: {name}")
        self.status_detail.setText(labels.get(status, status).capitalize())
        if status == "error":
            self.log_toggle.setChecked(True)

    def _update_render_progress(self, fraction: float):
        index, total, _name = self._current_video
        if not total:
            return
        self._set_overall_progress((index - 1 + fraction) / total)
        now = time.monotonic()
        if self._render_origin is None:
            self._render_origin = (now, fraction)
        started_at, start_fraction = self._render_origin
        text = f"Renderowanie: {fraction * 100:.0f}%"
        if fraction - start_fraction > 0.03:
            remaining = (now - started_at) / (fraction - start_fraction) * (1 - fraction)
            text += f" · zostało ok. {format_duration(remaining)}"
        self.status_detail.setText(text)

    def _notify(self, title: str, message: str):
        """Powiadomienie systemowe po długiej pracy, gdy okno nie jest na wierzchu."""
        QApplication.alert(self)
        if self.isActiveWindow() or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self.tray_icon is None:
            self.tray_icon = QSystemTrayIcon(icon("film", self.colors["accent"]), self)
            self.tray_icon.setToolTip("IPSC Video Automato")
            self.tray_icon.messageClicked.connect(self._bring_to_front)
        self.tray_icon.show()
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 10000)
        QTimer.singleShot(15000, self.tray_icon.hide)

    def _bring_to_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _finish(self, success: bool, message: str):
        self.job_complete = True
        if self.worker_thread is None:
            self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.cancel_event = None
        self.status.setText(message)
        if success:
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.status_detail.setText("Sprawdź filmy w folderze Gotowe, a potem opublikuj je w zakładce YouTube lub Buffer.")
            self._notify("Montaż zakończony", message)
        elif "przerwano" in message.lower():
            self.status_detail.setText("Wcześniej gotowe filmy zostały zachowane.")
            self.log_view.appendPlainText(message)
        else:
            self.status_detail.setText("Szczegóły są w dzienniku poniżej.")
            self.log_toggle.setChecked(True)
            self._notify("Montaż zakończony z błędami", message)

    def _cleanup_thread(self):
        self.worker = None
        self.worker_thread = None
        if self.job_complete:
            self.start_button.setEnabled(True)

    def closeEvent(self, event):
        if self.test_thread is not None:
            self.test_thread.quit()
            self.test_thread.wait(5000)
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.information(
                self,
                "Montaż w toku",
                "Poczekaj na zakończenie montażu przed zamknięciem aplikacji.",
            )
            event.ignore()
            return
        if self.yt_thread and self.yt_thread.isRunning():
            QMessageBox.information(
                self,
                "Wysyłanie w toku",
                "Przerwij wysyłanie na YouTube i poczekaj na jego zakończenie przed zamknięciem aplikacji.",
            )
            event.ignore()
            return
        if self.buffer_thread and self.buffer_thread.isRunning():
            QMessageBox.information(
                self,
                "Tworzenie szkiców w toku",
                "Przerwij tworzenie szkiców w Buffer i poczekaj na jego zakończenie przed zamknięciem aplikacji.",
            )
            event.ignore()
            return
        if self.cloudflare_thread and self.cloudflare_thread.isRunning():
            QMessageBox.information(
                self,
                "Wysyłanie do Cloudflare w toku",
                "Przerwij wysyłkę do Cloudflare i poczekaj na jej zakończenie przed zamknięciem aplikacji.",
            )
            event.ignore()
            return
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IPSC Video Automato")
    # Fusion wygląda i zachowuje się tak samo na Windows i macOS, a motyw nadaje mu kolory.
    app.setStyle("Fusion")
    window = MainWindow()
    app.setWindowIcon(icon("film", window.colors["accent"]))
    window.show()
    QTimer.singleShot(300, window._test_on_startup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
