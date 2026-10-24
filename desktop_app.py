import re
import sys
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
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Signal
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
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from dataclasses import dataclass
from file_migration import fix_path, move_old_files
from app_settings import (
    SETTINGS_FILE,
    ensure_settings_file,
    saved_buffer_api_key,
    saved_cloudflare_settings,
    saved_imagemagick_path,
    save_imagemagick_path,
)
from system_check import format_html, run_system_check

PROJECT_DIR = Path(__file__).resolve().parent
WEEKDAY_NAMES = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]
PUBLISH_TIMES = [f"{g:02d}:{m:02d}" for g in range(24) for m in range(0, 60, 15)]
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


BUFFER_VIDEO_LIST_PATH = str(PROJECT_DIR / "buffer.txt")
RESULTS_MODES = (
    (TRYB_WYNIKOW_PRACTISCORE, "Practiscore"),
    (TRYB_WYNIKOW_ECM, "ECM"),
    (TRYB_WYNIKOW_TRENING, "Trening"),
)


class AssemblyWorker(QObject):
    log = Signal(str)
    progress = Signal(int, int, str, str)
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
        elif status == "done":
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
        self.setWindowTitle("IPSC Video Automato")
        self.resize(1120, 850)
        self.setMinimumSize(860, 680)
        self._build_ui()
        self._load_settings()
        self._load_startup_files()

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
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #10151d; color: #e7edf5; }
            QWidget { font-family: "Segoe UI", sans-serif; font-size: 10pt; }
            QLabel#brand { color: #43e0c1; font-size: 17pt; font-weight: 800; }
            QLabel#brandTitle { color: #f3f6fa; font-size: 17pt; font-weight: 700; letter-spacing: 1px; }
            QLabel#eyebrow { color: #8492a6; font-size: 8pt; letter-spacing: 1px; }
            QLabel#subtitle { color: #91a0b4; font-size: 10pt; padding-bottom: 3px; }
            QTabWidget::pane { border: 1px solid #283343; border-radius: 12px; top: -1px; }
            QTabBar::tab { background: #171f2a; color: #93a2b6; padding: 12px 18px; margin-right: 5px;
                           border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: #202b39; color: #53e2c3; font-weight: 700; }
            QGroupBox { background: #171f2a; border: 1px solid #283343; border-radius: 11px;
                        margin-top: 12px; padding: 18px 16px 14px; font-weight: 650; }
            QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #c7d2e0; }
            QLineEdit, QPlainTextEdit { background: #0f151d; color: #e7edf5; border: 1px solid #344255;
                                        border-radius: 7px; padding: 9px 11px; selection-background-color: #147d72; }
            QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #43cdb1; }
            QPlainTextEdit { font-family: "Cascadia Code", "Consolas", monospace; }
            QPushButton { background: #263344; color: #dce6f1; border: 1px solid #39495e;
                          border-radius: 7px; padding: 9px 14px; font-weight: 600; }
            QPushButton:hover { background: #33445a; border-color: #4e647e; }
            QPushButton:disabled { color: #738095; background: #202a37; }
            QPushButton#primary { background: #087f70; border: 1px solid #14a18b; color: white;
                                  padding: 11px 20px; font-size: 10pt; }
            QPushButton#primary:hover { background: #099782; }
            QPushButton#danger { color: #ffc2c2; border-color: #70434a; background: #35252b; }
            QLabel#muted { color: #8998ac; }
            QRadioButton { spacing: 8px; padding: 4px 8px; background: transparent; }
            QCheckBox { spacing: 8px; padding: 4px 2px; background: transparent; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;
                                   border: 2px solid #4e647e; background: #0f151d; }
            QCheckBox::indicator:checked { border-color: #43cdb1; background: #24b99f; }
            QRadioButton::indicator { width: 16px; height: 16px; border-radius: 9px;
                                      border: 2px solid #4e647e; background: #0f151d; }
            QRadioButton::indicator:checked { border-color: #43cdb1; background: #24b99f; }
            QPushButton#helpButton { padding: 0; border-radius: 15px; font-weight: 800; color: #53e2c3; }
            QToolTip { background: #202b39; color: #e7edf5; border: 1px solid #43cdb1; padding: 6px 8px; }
            QLabel#fileStatus { color: #91a0b4; font-size: 9pt; }
            QTextBrowser { background: #0f151d; border: 1px solid #283343; border-radius: 10px; padding: 14px; }
            QProgressBar { background: #0c1118; border: 1px solid #2d3949; border-radius: 5px;
                           height: 12px; text-align: center; color: transparent; }
            QProgressBar::chunk { background: #24b99f; border-radius: 4px; }
            QScrollBar:vertical { background: #111821; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #344255; min-height: 24px; border-radius: 4px; }
            """
        )

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
        self.subtitles_check = QCheckBox("Czy dodać napisy")
        self.subtitles_check.setToolTip(
            "Steruje tylko planszą z wynikami na dole filmu. Teksty wideo zależą od zawartości pliku tekstów."
        )
        self.subtitles_check.setChecked(
            str(self.settings.value("dodaj_napisy", "false")).lower() == "true"
        )
        self.subtitles_check.toggled.connect(self._remember_subtitles)
        layout.addWidget(self.subtitles_check)
        layout.addWidget(paths)

        bar = QHBoxLayout()
        self.status = QLabel("Gotowy do pracy")
        self.status.setObjectName("muted")
        self.start_button = QPushButton("▶  Rozpocznij montaż")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(44)
        self.start_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("Przerwij generowanie")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setMinimumHeight(44)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        bar.addWidget(self.status, 1)
        bar.addWidget(self.start_button)
        bar.addWidget(self.cancel_button)
        layout.addLayout(bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        log_group = QGroupBox("Dziennik pracy")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Tutaj pojawią się postęp montażu i komunikaty aplikacji.")
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group, 1)
        return page

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
            "Logo pojawi się w prawym górnym rogu (maks. 250×250 px, proporcje zachowane). "
            "Puste pole = bez logo."
        )
        logo_hint.setObjectName("muted")
        logo_hint.setWordWrap(True)
        logo_layout.addWidget(logo_hint)
        layout.addWidget(logo)
        layout.addWidget(self._build_imagemagick())
        layout.addWidget(self._create_editor("plik_z_tekstami", "Teksty wideo"))
        layout.addWidget(self._create_editor("plik_opisu_zawodow", "Opis zawodów"))
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
        self.yt_start = QPushButton("⬆  Wyślij do YT")
        self.yt_start.setObjectName("primary")
        self.yt_start.setMinimumHeight(44)
        self.yt_start.clicked.connect(self._send_to_yt)
        self.yt_cancel = QPushButton("Przerwij wysyłanie")
        self.yt_cancel.setObjectName("danger")
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
        self.buffer_send = QPushButton("⬆  Utwórz szkice w Buffer")
        self.buffer_send.setObjectName("primary")
        self.buffer_send.setMinimumHeight(44)
        self.buffer_send.clicked.connect(self._send_to_buffer)
        self.buffer_cancel = QPushButton("Przerwij")
        self.buffer_cancel.setObjectName("danger")
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
            counter.setStyleSheet("color: #ff7b7b;" if over_limit else "")

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
            QMessageBox.warning(self, "Buffer", "Brak klucza BUFFER_API w pliku settings.json.")
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
        browse_button.clicked.connect(self._choose_cloudflare_folder)
        row.addWidget(label)
        row.addWidget(self.cloudflare_folder, 1)
        row.addWidget(browse_button)
        layout.addLayout(row)

        bar = QHBoxLayout()
        self.cloudflare_status = QLabel("Gotowe do wysyłki")
        self.cloudflare_status.setObjectName("muted")
        self.cloudflare_send = QPushButton("⬆  Wyślij do CloudFlare")
        self.cloudflare_send.setMinimumHeight(40)
        self.cloudflare_send.clicked.connect(self._send_to_cloudflare)
        self.cloudflare_cancel = QPushButton("Przerwij")
        self.cloudflare_cancel.setObjectName("danger")
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

    def _build_imagemagick(self):
        group = QGroupBox("ImageMagick (napisy)")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        label = QLabel("Program magick")
        label.setMinimumWidth(150)
        self.imagemagick_field = QLineEdit(saved_imagemagick_path())
        self.imagemagick_field.setClearButtonEnabled(True)
        self.imagemagick_field.setPlaceholderText("Pusto = automatyczne wyszukiwanie w PATH")
        self.imagemagick_field.editingFinished.connect(self._save_imagemagick)
        button = QPushButton("Przeglądaj…")
        button.clicked.connect(self._choose_imagemagick)
        row.addWidget(label)
        row.addWidget(self.imagemagick_field, 1)
        row.addWidget(button)
        layout.addLayout(row)
        self.imagemagick_status = QLabel("")
        self.imagemagick_status.setObjectName("fileStatus")
        layout.addWidget(self.imagemagick_status)
        self._show_imagemagick_status()
        return group

    def _choose_imagemagick(self, checked: bool = False):
        del checked
        current = self.imagemagick_field.text().strip()
        file_filter = "Program (*.exe);;Wszystkie pliki (*)" if sys.platform == "win32" else "Wszystkie pliki (*)"
        path, _ = QFileDialog.getOpenFileName(
            self, "Wskaż program ImageMagick (magick)", current or str(Path.home()), file_filter
        )
        if path:
            self.imagemagick_field.setText(str(Path(path)))
            self._save_imagemagick()

    def _save_imagemagick(self):
        path = self.imagemagick_field.text().strip()
        try:
            save_imagemagick_path(path)
        except OSError as error:
            self.imagemagick_status.setText(f"Nie udało się zapisać settings.json: {error}")
            return
        self._show_imagemagick_status()

    def _show_imagemagick_status(self):
        path = self.imagemagick_field.text().strip()
        if not path:
            self.imagemagick_status.setText(f"Zapisano w {SETTINGS_FILE.name}: automatyczne wyszukiwanie w PATH")
        elif Path(path).is_file():
            self.imagemagick_status.setText(f"Zapisano w {SETTINGS_FILE.name}: {path}")
        else:
            self.imagemagick_status.setText(
                f"Zapisano w {SETTINGS_FILE.name}, ale plik nie istnieje — użyty zostanie ImageMagick z PATH"
            )

    def _build_help_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        bar = QHBoxLayout()
        description = QLabel("Sprawdź wymagane biblioteki Pythona oraz FFmpeg i ImageMagick.")
        description.setObjectName("muted")
        self.test_button = QPushButton("🩺  Test Systemu")
        self.test_button.setObjectName("primary")
        self.test_button.clicked.connect(self._run_system_test)
        bar.addWidget(description, 1)
        bar.addWidget(self.test_button)
        layout.addLayout(bar)

        self.test_results = QTextBrowser()
        self.test_results.setMaximumHeight(320)
        self.test_results.setVisible(False)
        layout.addWidget(self.test_results)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.document().setDefaultStyleSheet(
            "h1, h2, h3 { color: #43e0c1; } a { color: #6cb6ff; } "
            "code, pre { color: #f0c987; background: #1b2531; } "
            "th, td { padding: 4px 8px; }"
        )
        readme_path = Path(__file__).resolve().parent / "README.md"
        try:
            browser.setMarkdown(readme_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as error:
            browser.setPlainText(f"Nie udało się wczytać pliku pomocy:\n{readme_path}\n\n{error}")
        layout.addWidget(browser)
        return page

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
        self.test_button.setText("🩺  Test Systemu")
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
        button.clicked.connect(partial(self._choose_path, key, kind))
        row.addWidget(label_widget)
        row.addWidget(field, 1)
        row.addWidget(button)
        layout.addLayout(row)

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
        load_button = QPushButton("Wczytaj z pliku")
        load_button.clicked.connect(partial(self._load_file, key, True))
        save_button = QPushButton("Zapisz do pliku")
        save_button.clicked.connect(partial(self._save_file, key, True))
        controls.addWidget(load_button)
        controls.addWidget(save_button)
        layout.addLayout(controls)
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
        if key in self.editors and key in self._dirty_editors:
            decision = QMessageBox.warning(
                self,
                "Niezapisane zmiany",
                "Edytor zawiera niezapisane zmiany. Zapisać je przed wyborem innego pliku?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if decision == QMessageBox.Cancel:
                return
            if decision == QMessageBox.Save and not self._save_file(key):
                return
            if decision == QMessageBox.Discard:
                self._dirty_editors.discard(key)

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
        self.editor_status[key].setText("Niezapisane zmiany")

    def _load_file(self, key: str, show_error: bool = True, checked: bool = False):
        del checked
        if key in self._dirty_editors and show_error:
            decision = QMessageBox.question(
                self,
                "Niezapisane zmiany",
                "Wczytanie pliku zastąpi niezapisany tekst. Kontynuować?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if decision != QMessageBox.Yes:
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
        self.editor_status[key].setText(f"Zapisano: {path.name}")
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
            if key in self._dirty_editors and not self._save_file(key):
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
            if key in self.SUBTITLE_PATH_KEYS and not config.dodaj_napisy:
                continue
            if kind == "dir" and not path.is_dir():
                QMessageBox.warning(self, "Nieprawidłowa ścieżka", f"{label}: folder nie istnieje.\n{path}")
                return
            if kind == "file" and not path.is_file():
                QMessageBox.warning(self, "Nieprawidłowa ścieżka", f"{label}: plik nie istnieje.\n{path}")
                return

        try:
            videos = [
                file for file in config.folder_wejsciowy.iterdir()
                if file.suffix.lower() in {".mp4", ".mov"} and "TEMP_MPY_" not in file.name.upper()
            ]
        except OSError as error:
            QMessageBox.warning(self, "Błąd folderu", f"Nie można odczytać nagrań:\n{error}")
            return
        if not videos:
            QMessageBox.warning(self, "Brak nagrań", "Folder źródłowy nie zawiera filmów MP4 ani MOV.")
            return

        for key, _, _ in self.PATHS:
            self.settings.setValue(key, str(getattr(config, key)))
        self.log_view.clear()
        self.status.setText("Przygotowywanie montażu…")
        self.progress_bar.setRange(0, len(videos))
        self.progress_bar.setValue(0)
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
        self.status.setText("Przerywanie generowania…")
        self._append_log("Żądanie przerwania wysłane. Trwa bezpieczne zatrzymywanie bieżącego etapu.")

    def _append_log(self, text: str):
        self.log_view.appendPlainText(text)

    def _update_progress(self, index: int, total: int, name: str, status: str):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(index)
        labels = {
            "done": "gotowe",
            "error": "błąd",
            "skipped": "pominięto",
            "cancelled": "przerwano",
        }
        self.status.setText(f"{index}/{total}: {name} — {labels.get(status, status)}")

    def _finish(self, success: bool, message: str):
        self.job_complete = True
        if self.worker_thread is None:
            self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.cancel_event = None
        self.status.setText(message)
        if success:
            self.progress_bar.setValue(self.progress_bar.maximum())
        if not success and "przerwano" not in message.lower():
            QMessageBox.warning(self, "Montaż zakończony z błędem", message)
        elif not success:
            self.log_view.append(message)

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
    window = MainWindow()
    window.show()
    QTimer.singleShot(300, window._test_on_startup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
