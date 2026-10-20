import sys
from pathlib import Path

try:
    import PySide6.QtWidgets  # noqa: F401
except ImportError:
    from sprawdzanie_systemu import pokaz_raport_bez_qt
    pokaz_raport_bez_qt()
    sys.exit(1)

from functools import partial
from threading import Event
from typing import Dict, Optional
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from dataclasses import dataclass
from migracja_plikow import popraw_sciezke, przenies_stare_pliki
from ustawienia_aplikacji import (
    PLIK_USTAWIEN,
    zapewnij_plik_ustawien,
    zapisana_sciezka_imagemagick,
    zapisz_sciezke_imagemagick,
)
from sprawdzanie_systemu import formatuj_html, uruchom_test_systemu

PROJEKT = Path(__file__).resolve().parent
przenies_stare_pliki(PROJEKT)
zapewnij_plik_ustawien()

try:
    from ipsc_automato import (
        FOLDER_MUZYKI,
        FOLDER_WEJSCIOWY,
        FOLDER_WYJSCIOWY,
        PLIK_OPISU_ZAWODOW,
        PLIK_Z_TEKSTAMI,
        PLIK_Z_TORAMI,
        PLIK_Z_WYNIKAMI,
        KonfiguracjaSciezek,
        uruchom_automatyzacje,
    )
    BLAD_MONTAZU = ""
except Exception as blad_importu:
    # Brak biblioteki/programu nie może uniemożliwić uruchomienia okna z zakładką Pomoc.
    BLAD_MONTAZU = f"{type(blad_importu).__name__}: {blad_importu}"
    FOLDER_WEJSCIOWY = str(PROJEKT / "Surowe")
    FOLDER_WYJSCIOWY = str(PROJEKT / "Gotowe")
    FOLDER_MUZYKI = str(PROJEKT / "Muzyka")
    PLIK_Z_WYNIKAMI = str(PROJEKT / "wyniki.txt")
    PLIK_Z_TEKSTAMI = str(PROJEKT / "teksty_wideo.txt")
    PLIK_Z_TORAMI = str(PROJEKT / "mapowanie_torow.txt")
    PLIK_OPISU_ZAWODOW = str(PROJEKT / "opis_zawodow.txt")
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


class MontazWorker(QObject):
    log = Signal(str)
    progress = Signal(int, int, str, str)
    completed = Signal(bool, str)

    def __init__(self, konfiguracja: KonfiguracjaSciezek, cancel_event: Event):
        super().__init__()
        self.konfiguracja = konfiguracja
        self.cancel_event = cancel_event
        self.error_count = 0
        self.completed_count = 0
        self.skipped_count = 0

    def run(self):
        try:
            sukces = uruchom_automatyzacje(
                konfiguracja=self.konfiguracja,
                log_callback=self.log.emit,
                progress_callback=self._raportuj_postep,
                cancel_event=self.cancel_event,
            )
        except Exception as blad:
            self.log.emit(f"BŁĄD: {blad}")
            self.completed.emit(False, str(blad))
            return

        if not sukces and self.cancel_event.is_set():
            self.completed.emit(False, "Generowanie przerwano przez użytkownika.")
        elif self.skipped_count and not self.completed_count and not self.error_count:
            self.completed.emit(
                False,
                "Wszystkie nagrania pominięto: sprawdź, czy wyniki zawierają przypisane tory.",
            )
        elif not sukces or self.error_count:
            self.completed.emit(
                False,
                "Montaż nie powiódł się. Sprawdź log i wymagania systemowe."
                if not self.error_count
                else f"Montaż zakończony z błędami ({self.error_count} filmów). Sprawdź log.",
            )
        else:
            self.completed.emit(True, "Montaż zakończony.")

    def _raportuj_postep(self, indeks: int, razem: int, nazwa: str, status: str):
        if status == "error":
            self.error_count += 1
        elif status == "done":
            self.completed_count += 1
        elif status == "skipped":
            self.skipped_count += 1
        self.progress.emit(indeks, razem, nazwa, status)


class YouTubeWorker(QObject):
    log = Signal(str)
    completed = Signal(bool, str)

    def __init__(self, folder: Path, opis: Path, publikuj: bool, cancel_event: Event):
        super().__init__()
        self.folder = folder
        self.opis = opis
        self.publikuj = publikuj
        self.cancel_event = cancel_event

    def run(self):
        try:
            import youtube_upload

            filmy = sorted(
                (p for p in self.folder.iterdir() if p.suffix.lower() == ".mp4"),
                key=lambda p: p.name.casefold(),
            )
            if not filmy:
                self.completed.emit(False, f"Brak plików MP4 w folderze: {self.folder}")
                return
            self.log.emit(f"[YT] Znaleziono filmów: {len(filmy)}")
            youtube_upload.wyslij_filmy(
                filmy,
                self.publikuj,
                plik_opisu=self.opis,
                log=self.log.emit,
                cancel_event=self.cancel_event,
            )
        except Exception as blad:
            if type(blad).__name__ == "WysylaniePrzerwane":
                self.completed.emit(False, "Wysyłanie przerwano przez użytkownika.")
            else:
                self.log.emit(f"[YT] BŁĄD: {blad}")
                self.completed.emit(False, f"Wysyłanie nie powiodło się: {blad}")
            return
        self.completed.emit(True, "Wysyłanie zakończone." if self.publikuj else "Podgląd zakończony.")


class SystemCheckWorker(QObject):
    finished = Signal(str, bool)

    def run(self):
        try:
            wyniki = uruchom_test_systemu()
            self.finished.emit(formatuj_html(wyniki), any(not w.ok for w in wyniki))
        except Exception as blad:
            self.finished.emit(f"<p style='color:#ff7b7b'>Test systemu nie powiódł się: {blad}</p>", True)


class MainWindow(QMainWindow):
    SCIEZKI = (
        ("folder_wejsciowy", "Nagrania źródłowe", "dir"),
        ("folder_wyjsciowy", "Gotowe filmy", "dir"),
        ("folder_muzyki", "Muzyka", "dir"),
        ("plik_z_wynikami", "Wyniki zawodów", "file"),
        ("plik_z_torami", "Mapowanie torów", "file"),
        ("plik_z_tekstami", "Teksty wideo", "file"),
        ("plik_opisu_zawodow", "Opis zawodów", "file"),
    )
    EDYTORY = (
        ("plik_z_tekstami", "Teksty wideo"),
        ("plik_opisu_zawodow", "Opis zawodów"),
        ("plik_z_torami", "Mapowanie torów"),
        ("plik_z_wynikami", "Wyniki zawodów"),
    )

    def __init__(self):
        super().__init__()
        self.settings = QSettings("YTAutoCut", "Desktop")
        self.fields: Dict[str, QLineEdit] = {}
        self.editors: Dict[str, QPlainTextEdit] = {}
        self.editor_status: Dict[str, QLabel] = {}
        self._dirty_editors = set()
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[MontazWorker] = None
        self.cancel_event: Optional[Event] = None
        self.yt_thread: Optional[QThread] = None
        self.yt_worker: Optional[YouTubeWorker] = None
        self.yt_cancel_event: Optional[Event] = None
        self.job_complete = False
        self.test_thread: Optional[QThread] = None
        self.test_worker: Optional[SystemCheckWorker] = None
        self._test_automatyczny = False
        self.setWindowTitle("IPSC Video Automato")
        self.resize(1120, 850)
        self.setMinimumSize(860, 680)
        self._zbuduj_interfejs()
        self._wczytaj_ustawienia()
        self._wczytaj_startowe_pliki()

    def _zbuduj_interfejs(self):
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 26, 30, 28)
        layout.setSpacing(18)

        naglowek = QHBoxLayout()
        logo = QLabel("IPSC")
        logo.setObjectName("brand")
        nazwa = QLabel("VIDEO AUTOMATO")
        nazwa.setObjectName("brandTitle")
        naglowek.addWidget(logo)
        naglowek.addWidget(nazwa)
        naglowek.addStretch(1)
        wersja = QLabel("WORKSPACE  /  2026")
        wersja.setObjectName("eyebrow")
        naglowek.addWidget(wersja)
        layout.addLayout(naglowek)

        opis = QLabel("Produkcja i organizacja materiałów wideo z zawodów")
        opis.setObjectName("subtitle")
        layout.addWidget(opis)

        self.tabs = QTabWidget()
        self.tab_glowna = self._zbuduj_glowna()
        self.tab_zawody = self._zbuduj_zawody()
        self.tab_konfiguracja = self._zbuduj_konfiguracje()
        self.tabs.addTab(self.tab_glowna, "  Główna  ")
        self.tabs.addTab(self.tab_zawody, "  Zawody  ")
        self.tabs.addTab(self.tab_konfiguracja, "  Konfiguracja  ")
        self.tabs.addTab(self._zbuduj_youtube(), "  YouTube  ")
        self.tab_pomoc = self._zbuduj_pomoc()
        self.tabs.addTab(self.tab_pomoc, "  Pomoc  ")
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

    def _zbuduj_glowna(self):
        strona = QWidget()
        layout = QVBoxLayout(strona)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        sciezki = QGroupBox("Projekt wideo")
        sciezki_layout = QVBoxLayout(sciezki)
        sciezki_layout.setSpacing(12)
        self._dodaj_pole_sciezki(sciezki_layout, "folder_wejsciowy", "Nagrania źródłowe", "dir")
        self._dodaj_pole_sciezki(sciezki_layout, "folder_wyjsciowy", "Gotowe filmy", "dir")
        layout.addWidget(sciezki)

        pasek = QHBoxLayout()
        self.status = QLabel("Gotowy do pracy")
        self.status.setObjectName("muted")
        self.start_button = QPushButton("▶  Rozpocznij montaż")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(44)
        self.start_button.clicked.connect(self._rozpocznij)
        self.cancel_button = QPushButton("Przerwij generowanie")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setMinimumHeight(44)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._przerwij)
        pasek.addWidget(self.status, 1)
        pasek.addWidget(self.start_button)
        pasek.addWidget(self.cancel_button)
        layout.addLayout(pasek)

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
        return strona

    def _zbuduj_konfiguracje(self):
        strona = QWidget()
        layout = QVBoxLayout(strona)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        opis = QLabel("Folder z podkładami oraz treści wykorzystywane przy generowaniu filmów.")
        opis.setObjectName("muted")
        layout.addWidget(opis)

        muzyka = QGroupBox("Biblioteka muzyki")
        muzyka_layout = QVBoxLayout(muzyka)
        self._dodaj_pole_sciezki(muzyka_layout, "folder_muzyki", "Folder z muzyką", "dir")
        layout.addWidget(muzyka)
        layout.addWidget(self._zbuduj_imagemagick())
        layout.addWidget(self._stworz_edytor("plik_z_tekstami", "Teksty wideo"))
        layout.addWidget(self._stworz_edytor("plik_opisu_zawodow", "Opis zawodów"))
        layout.addStretch(1)
        return strona

    def _zbuduj_youtube(self):
        strona = QWidget()
        layout = QVBoxLayout(strona)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        opis = QLabel("Wysyłanie gotowych filmów (Shorts) na YouTube z planowaniem publikacji.")
        opis.setObjectName("muted")
        layout.addWidget(opis)

        grupa = QGroupBox("Folder z filmami do wysłania")
        grupa_layout = QVBoxLayout(grupa)
        self.yt_ten_sam_folder = QCheckBox("Taki sam jak „Gotowe filmy” (zakładka Główna)")
        self.yt_ten_sam_folder.setChecked(
            str(self.settings.value("yt_ten_sam_folder", "true")).lower() == "true"
        )
        self.yt_ten_sam_folder.toggled.connect(self._zmien_tryb_folderu_yt)
        grupa_layout.addWidget(self.yt_ten_sam_folder)
        wiersz = QHBoxLayout()
        etykieta = QLabel("Folder YouTube")
        etykieta.setMinimumWidth(150)
        self.yt_folder = QLineEdit(str(self.settings.value("folder_youtube", "")))
        self.yt_folder.setPlaceholderText("Wskaż folder z plikami MP4…")
        self.yt_folder.editingFinished.connect(
            lambda: self.settings.setValue("folder_youtube", self.yt_folder.text().strip())
        )
        self.yt_przegladaj = QPushButton("Przeglądaj…")
        self.yt_przegladaj.clicked.connect(self._wybierz_folder_yt)
        wiersz.addWidget(etykieta)
        wiersz.addWidget(self.yt_folder, 1)
        wiersz.addWidget(self.yt_przegladaj)
        grupa_layout.addLayout(wiersz)
        layout.addWidget(grupa)

        self.yt_podglad = QCheckBox("Tylko podgląd (pokaż tytuły i terminy, bez wysyłania)")
        layout.addWidget(self.yt_podglad)

        pasek = QHBoxLayout()
        self.yt_status = QLabel("Gotowy do wysyłania")
        self.yt_status.setObjectName("muted")
        self.yt_start = QPushButton("⬆  Wyślij do YT")
        self.yt_start.setObjectName("primary")
        self.yt_start.setMinimumHeight(44)
        self.yt_start.clicked.connect(self._wyslij_do_yt)
        self.yt_cancel = QPushButton("Przerwij wysyłanie")
        self.yt_cancel.setObjectName("danger")
        self.yt_cancel.setMinimumHeight(44)
        self.yt_cancel.setEnabled(False)
        self.yt_cancel.clicked.connect(self._przerwij_yt)
        pasek.addWidget(self.yt_status, 1)
        pasek.addWidget(self.yt_start)
        pasek.addWidget(self.yt_cancel)
        layout.addLayout(pasek)

        log_group = QGroupBox("Dziennik wysyłania")
        log_layout = QVBoxLayout(log_group)
        self.yt_log = QPlainTextEdit()
        self.yt_log.setReadOnly(True)
        self.yt_log.setPlaceholderText("Tutaj pojawią się komunikaty z wysyłania na YouTube.")
        log_layout.addWidget(self.yt_log)
        layout.addWidget(log_group, 1)

        self.fields["folder_wyjsciowy"].textChanged.connect(self._odswiez_folder_yt)
        self._zmien_tryb_folderu_yt()
        return strona

    def _zmien_tryb_folderu_yt(self, checked: bool = False):
        del checked
        wspolny = self.yt_ten_sam_folder.isChecked()
        self.settings.setValue("yt_ten_sam_folder", "true" if wspolny else "false")
        self.yt_folder.setEnabled(not wspolny)
        self.yt_przegladaj.setEnabled(not wspolny)
        self._odswiez_folder_yt()

    def _odswiez_folder_yt(self, *_):
        if self.yt_ten_sam_folder.isChecked():
            self.yt_folder.setText(self.fields["folder_wyjsciowy"].text().strip())

    def _wybierz_folder_yt(self, checked: bool = False):
        del checked
        start = self.yt_folder.text().strip() or str(PROJEKT)
        wybrany = QFileDialog.getExistingDirectory(self, "Folder z filmami do wysłania", start)
        if wybrany:
            self.yt_folder.setText(wybrany)
            self.settings.setValue("folder_youtube", wybrany)

    def _folder_yt(self) -> Path:
        pole = self.fields["folder_wyjsciowy"] if self.yt_ten_sam_folder.isChecked() else self.yt_folder
        return Path(pole.text().strip())

    def _wyslij_do_yt(self, checked: bool = False):
        del checked
        folder = self._folder_yt()
        if not folder.is_dir():
            QMessageBox.warning(self, "Nieprawidłowy folder", f"Folder nie istnieje:\n{folder}")
            return
        publikuj = not self.yt_podglad.isChecked()
        if publikuj and QMessageBox.question(
            self,
            "Wysyłanie na YouTube",
            f"Wysłać filmy MP4 z folderu:\n{folder}\n\nna YouTube (prywatne, z zaplanowaną publikacją)?",
        ) != QMessageBox.Yes:
            return
        self.yt_log.clear()
        self.yt_status.setText("Wysyłanie…" if publikuj else "Sprawdzanie (podgląd)…")
        self.yt_start.setEnabled(False)
        self.yt_cancel.setEnabled(True)
        self.yt_cancel_event = Event()
        self.yt_thread = QThread(self)
        self.yt_worker = YouTubeWorker(
            folder, Path(self.fields["plik_opisu_zawodow"].text().strip()), publikuj, self.yt_cancel_event
        )
        self.yt_worker.moveToThread(self.yt_thread)
        self.yt_thread.started.connect(self.yt_worker.run)
        self.yt_worker.log.connect(self.yt_log.appendPlainText)
        self.yt_worker.completed.connect(self._zakoncz_yt)
        self.yt_worker.completed.connect(self.yt_thread.quit)
        self.yt_worker.completed.connect(self.yt_worker.deleteLater)
        self.yt_thread.finished.connect(self.yt_thread.deleteLater)
        self.yt_thread.finished.connect(self._posprzataj_yt)
        self.yt_thread.start()

    def _przerwij_yt(self, checked: bool = False):
        del checked
        if self.yt_cancel_event is None or self.yt_cancel_event.is_set():
            return
        self.yt_cancel_event.set()
        self.yt_cancel.setEnabled(False)
        self.yt_status.setText("Przerywanie wysyłania…")
        self.yt_log.appendPlainText("Żądanie przerwania wysłane. Wysyłanie zatrzyma się po bieżącym fragmencie pliku.")

    def _zakoncz_yt(self, sukces: bool, komunikat: str):
        self.yt_status.setText(komunikat)
        self.yt_cancel.setEnabled(False)
        self.yt_cancel_event = None
        if sukces:
            self.yt_log.appendPlainText(komunikat)
        elif "przerwano" in komunikat.lower():
            self.yt_log.appendPlainText(komunikat)
        else:
            QMessageBox.warning(self, "YouTube", komunikat)

    def _posprzataj_yt(self):
        self.yt_worker = None
        self.yt_thread = None
        self.yt_start.setEnabled(True)

    def _zbuduj_imagemagick(self):
        grupa = QGroupBox("ImageMagick (napisy)")
        layout = QVBoxLayout(grupa)
        wiersz = QHBoxLayout()
        etykieta = QLabel("Program magick")
        etykieta.setMinimumWidth(150)
        self.pole_imagemagick = QLineEdit(zapisana_sciezka_imagemagick())
        self.pole_imagemagick.setClearButtonEnabled(True)
        self.pole_imagemagick.setPlaceholderText("Pusto = automatyczne wyszukiwanie w PATH")
        self.pole_imagemagick.editingFinished.connect(self._zapisz_imagemagick)
        przycisk = QPushButton("Przeglądaj…")
        przycisk.clicked.connect(self._wybierz_imagemagick)
        wiersz.addWidget(etykieta)
        wiersz.addWidget(self.pole_imagemagick, 1)
        wiersz.addWidget(przycisk)
        layout.addLayout(wiersz)
        self.status_imagemagick = QLabel("")
        self.status_imagemagick.setObjectName("fileStatus")
        layout.addWidget(self.status_imagemagick)
        self._pokaz_status_imagemagick()
        return grupa

    def _wybierz_imagemagick(self, checked: bool = False):
        del checked
        aktualna = self.pole_imagemagick.text().strip()
        filtr = "Program (*.exe);;Wszystkie pliki (*)" if sys.platform == "win32" else "Wszystkie pliki (*)"
        sciezka, _ = QFileDialog.getOpenFileName(
            self, "Wskaż program ImageMagick (magick)", aktualna or str(Path.home()), filtr
        )
        if sciezka:
            self.pole_imagemagick.setText(str(Path(sciezka)))
            self._zapisz_imagemagick()

    def _zapisz_imagemagick(self):
        sciezka = self.pole_imagemagick.text().strip()
        try:
            zapisz_sciezke_imagemagick(sciezka)
        except OSError as blad:
            self.status_imagemagick.setText(f"Nie udało się zapisać settings.json: {blad}")
            return
        self._pokaz_status_imagemagick()

    def _pokaz_status_imagemagick(self):
        sciezka = self.pole_imagemagick.text().strip()
        if not sciezka:
            self.status_imagemagick.setText(f"Zapisano w {PLIK_USTAWIEN.name}: automatyczne wyszukiwanie w PATH")
        elif Path(sciezka).is_file():
            self.status_imagemagick.setText(f"Zapisano w {PLIK_USTAWIEN.name}: {sciezka}")
        else:
            self.status_imagemagick.setText(
                f"Zapisano w {PLIK_USTAWIEN.name}, ale plik nie istnieje — użyty zostanie ImageMagick z PATH"
            )

    def _zbuduj_pomoc(self):
        strona = QWidget()
        layout = QVBoxLayout(strona)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        pasek = QHBoxLayout()
        opis = QLabel("Sprawdź wymagane biblioteki Pythona oraz FFmpeg i ImageMagick.")
        opis.setObjectName("muted")
        self.test_button = QPushButton("🩺  Test Systemu")
        self.test_button.setObjectName("primary")
        self.test_button.clicked.connect(self._uruchom_test_systemu)
        pasek.addWidget(opis, 1)
        pasek.addWidget(self.test_button)
        layout.addLayout(pasek)

        self.test_wyniki = QTextBrowser()
        self.test_wyniki.setMaximumHeight(320)
        self.test_wyniki.setVisible(False)
        layout.addWidget(self.test_wyniki)

        przegladarka = QTextBrowser()
        przegladarka.setOpenExternalLinks(True)
        przegladarka.document().setDefaultStyleSheet(
            "h1, h2, h3 { color: #43e0c1; } a { color: #6cb6ff; } "
            "code, pre { color: #f0c987; background: #1b2531; } "
            "th, td { padding: 4px 8px; }"
        )
        plik = Path(__file__).resolve().parent / "README.md"
        try:
            przegladarka.setMarkdown(plik.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as blad:
            przegladarka.setPlainText(f"Nie udało się wczytać pliku pomocy:\n{plik}\n\n{blad}")
        layout.addWidget(przegladarka)
        return strona

    def _uruchom_test_systemu(self, checked: bool = False, automatycznie: bool = False):
        del checked
        if self.test_thread is not None:
            return
        self._test_automatyczny = automatycznie
        self.test_button.setEnabled(False)
        self.test_button.setText("Trwa testowanie…")
        self.test_wyniki.setVisible(True)
        self.test_wyniki.setHtml("<p>Sprawdzanie systemu, to może potrwać kilka sekund…</p>")
        self.test_thread = QThread(self)
        self.test_worker = SystemCheckWorker()
        self.test_worker.moveToThread(self.test_thread)
        self.test_thread.started.connect(self.test_worker.run)
        self.test_worker.finished.connect(self._pokaz_wynik_testu)
        self.test_worker.finished.connect(self.test_thread.quit)
        self.test_thread.finished.connect(self.test_worker.deleteLater)
        self.test_thread.finished.connect(self.test_thread.deleteLater)
        self.test_thread.finished.connect(self._zwolnij_watek_testu)
        self.test_thread.start()

    def _zwolnij_watek_testu(self):
        self.test_thread = None
        self.test_worker = None

    def _test_przy_starcie(self):
        self._uruchom_test_systemu(automatycznie=True)

    def _pokaz_wynik_testu(self, html: str, problemy: bool):
        if self._test_automatyczny and not problemy:
            self.test_wyniki.setVisible(False)
        else:
            self.test_wyniki.setHtml(html)
        self.test_button.setEnabled(True)
        self.test_button.setText("🩺  Test Systemu")
        if self._test_automatyczny and problemy:
            self.tabs.setCurrentWidget(self.tab_pomoc)
            self.status.setText("Wykryto braki w systemie — szczegóły w zakładce Pomoc")

    def _zbuduj_zawody(self):
        strona = QWidget()
        layout = QVBoxLayout(strona)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        opis = QLabel("Edytuj dane zawodów bezpośrednio w plikach tekstowych używanych przez montaż.")
        opis.setObjectName("muted")
        layout.addWidget(opis)
        mapowanie = self._stworz_edytor("plik_z_torami", "Mapowanie torów")
        mapowanie.layout().insertLayout(1, self._zbuduj_wybor_orientacji())
        layout.addWidget(mapowanie)
        layout.addWidget(self._stworz_edytor("plik_z_wynikami", "Wyniki zawodów"))
        layout.addStretch(1)
        return strona

    def _zbuduj_wybor_orientacji(self):
        wiersz = QHBoxLayout()
        etykieta = QLabel("Rodzaj wszystkich filmów:")
        self.radio_pionowe = QRadioButton("Wideo Pionowe")
        self.radio_poziome = QRadioButton("Wideo Poziome")
        grupa = QButtonGroup(self)
        grupa.addButton(self.radio_pionowe)
        grupa.addButton(self.radio_poziome)
        zapamietana = str(self.settings.value("domyslna_orientacja", "V")).upper()
        (self.radio_poziome if zapamietana == "H" else self.radio_pionowe).setChecked(True)
        self.radio_pionowe.toggled.connect(self._zapamietaj_orientacje)

        pomoc = QPushButton("?")
        pomoc.setObjectName("helpButton")
        pomoc.setFixedSize(30, 30)
        pomoc.setCursor(Qt.PointingHandCursor)
        pomoc.setToolTip("Jeżeli chcesz by każdy plik był innego rodzaju przeczytaj pomoc")
        pomoc.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_pomoc))

        wiersz.addWidget(etykieta)
        wiersz.addWidget(self.radio_pionowe)
        wiersz.addWidget(self.radio_poziome)
        wiersz.addWidget(pomoc)
        wiersz.addStretch(1)
        return wiersz

    def _zapamietaj_orientacje(self, checked: bool = False):
        del checked
        self.settings.setValue("domyslna_orientacja", self._domyslna_orientacja())

    def _domyslna_orientacja(self) -> str:
        return "H" if self.radio_poziome.isChecked() else "V"

    def _dodaj_pole_sciezki(self, layout, key: str, label: str, kind: str):
        wiersz = QHBoxLayout()
        etykieta = QLabel(label)
        etykieta.setMinimumWidth(150)
        pole = QLineEdit()
        pole.setClearButtonEnabled(True)
        pole.setPlaceholderText("Wskaż ścieżkę…")
        self.fields[key] = pole
        pole.editingFinished.connect(partial(self._zapamietaj_sciezke, key))
        przycisk = QPushButton("Przeglądaj…")
        przycisk.clicked.connect(partial(self._wybierz, key, kind))
        wiersz.addWidget(etykieta)
        wiersz.addWidget(pole, 1)
        wiersz.addWidget(przycisk)
        layout.addLayout(wiersz)

    def _stworz_edytor(self, key: str, title: str):
        grupa = QGroupBox(title)
        layout = QVBoxLayout(grupa)
        self._dodaj_pole_sciezki(layout, key, "Plik TXT", "file")

        editor = QPlainTextEdit()
        editor.setMinimumHeight(125)
        editor.setPlaceholderText(f"Wpisz lub wklej treść: {title.lower()}…")
        editor.textChanged.connect(partial(self._oznacz_zmiany, key))
        self.editors[key] = editor
        layout.addWidget(editor, 1)

        controls = QHBoxLayout()
        status = QLabel("Plik nie został jeszcze wczytany")
        status.setObjectName("fileStatus")
        self.editor_status[key] = status
        wczytaj = QPushButton("Wczytaj z pliku")
        wczytaj.clicked.connect(partial(self._wczytaj_plik, key, True))
        zapisz = QPushButton("Zapisz do pliku")
        zapisz.clicked.connect(partial(self._zapisz_plik, key, True))
        controls.addWidget(status, 1)
        controls.addWidget(wczytaj)
        controls.addWidget(zapisz)
        layout.addLayout(controls)
        return grupa

    def _domyslne_sciezki(self) -> KonfiguracjaSciezek:
        return KonfiguracjaSciezek(
            folder_wejsciowy=Path(FOLDER_WEJSCIOWY),
            folder_wyjsciowy=Path(FOLDER_WYJSCIOWY),
            folder_muzyki=Path(FOLDER_MUZYKI),
            plik_z_wynikami=Path(PLIK_Z_WYNIKAMI),
            plik_z_tekstami=Path(PLIK_Z_TEKSTAMI),
            plik_z_torami=Path(PLIK_Z_TORAMI),
            plik_opisu_zawodow=Path(PLIK_OPISU_ZAWODOW),
        )

    def _wczytaj_ustawienia(self):
        domyslne = self._domyslne_sciezki()
        for key, _, _ in self.SCIEZKI:
            wartosc = popraw_sciezke(self.settings.value(key, str(getattr(domyslne, key))))
            self.fields[key].setText(str(wartosc))

    def _wczytaj_startowe_pliki(self):
        for key, _ in self.EDYTORY:
            self._wczytaj_plik(key, False)

    def _wybierz(self, key: str, kind: str, checked: bool = False):
        del checked
        if key in self.editors and key in self._dirty_editors:
            decyzja = QMessageBox.warning(
                self,
                "Niezapisane zmiany",
                "Edytor zawiera niezapisane zmiany. Zapisać je przed wyborem innego pliku?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if decyzja == QMessageBox.Cancel:
                return
            if decyzja == QMessageBox.Save and not self._zapisz_plik(key):
                return
            if decyzja == QMessageBox.Discard:
                self._dirty_editors.discard(key)

        aktualna = Path(self.fields[key].text().strip() or ".")
        if kind == "dir":
            sciezka = QFileDialog.getExistingDirectory(self, "Wybierz folder", str(aktualna))
        else:
            sciezka, _ = QFileDialog.getOpenFileName(
                self, "Wybierz plik tekstowy", str(aktualna), "Pliki tekstowe (*.txt);;Wszystkie pliki (*)"
            )
        if sciezka:
            self.fields[key].setText(sciezka)
            self._zapamietaj_sciezke(key)
            if key in self.editors:
                self._wczytaj_plik(key, True)

    def _zapamietaj_sciezke(self, key: str):
        self.settings.setValue(key, self.fields[key].text().strip())

    def _oznacz_zmiany(self, key: str):
        self._dirty_editors.add(key)
        self.editor_status[key].setText("Niezapisane zmiany")

    def _wczytaj_plik(self, key: str, pokaz_blad: bool = True, checked: bool = False):
        del checked
        if key in self._dirty_editors and pokaz_blad:
            decyzja = QMessageBox.question(
                self,
                "Niezapisane zmiany",
                "Wczytanie pliku zastąpi niezapisany tekst. Kontynuować?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if decyzja != QMessageBox.Yes:
                return False

        sciezka = Path(self.fields[key].text().strip())
        try:
            zawartosc = sciezka.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as blad:
            komunikat = f"Nie udało się wczytać pliku:\n{sciezka}\n\n{blad}"
            self.editor_status[key].setText("Błąd odczytu pliku")
            if pokaz_blad:
                QMessageBox.warning(self, "Błąd odczytu", komunikat)
            else:
                self.editor_status[key].setToolTip(komunikat)
            return False

        editor = self.editors[key]
        editor.blockSignals(True)
        try:
            editor.setPlainText(zawartosc)
        finally:
            editor.blockSignals(False)
        self._dirty_editors.discard(key)
        self.editor_status[key].setText(f"Wczytano: {sciezka.name}")
        self.editor_status[key].setToolTip(str(sciezka))
        return True

    def _zapisz_plik(self, key: str, pokaz_potwierdzenie: bool = False, checked: bool = False):
        del checked
        sciezka = Path(self.fields[key].text().strip())
        try:
            sciezka.write_text(self.editors[key].toPlainText(), encoding="utf-8")
        except (OSError, UnicodeError) as blad:
            komunikat = f"Nie udało się zapisać pliku:\n{sciezka}\n\n{blad}"
            self.editor_status[key].setText("Błąd zapisu pliku")
            QMessageBox.warning(self, "Błąd zapisu", komunikat)
            return False

        self._dirty_editors.discard(key)
        self._zapamietaj_sciezke(key)
        self.editor_status[key].setText(f"Zapisano: {sciezka.name}")
        self.editor_status[key].setToolTip(str(sciezka))
        if pokaz_potwierdzenie:
            self.status.setText(f"Zapisano plik: {sciezka.name}")
        return True

    def _zapisz_zmienione_edytory(self):
        for key, _ in self.EDYTORY:
            if key in self._dirty_editors and not self._zapisz_plik(key):
                self.tabs.setCurrentWidget(
                    self.tab_konfiguracja if key in {"plik_z_tekstami", "plik_opisu_zawodow"} else self.tab_zawody
                )
                return False
        return True

    def _pobierz_konfiguracje(self) -> KonfiguracjaSciezek:
        return KonfiguracjaSciezek(
            **{
                key: Path(pole.text().strip())
                for key, pole in self.fields.items()
            },
            domyslna_orientacja=self._domyslna_orientacja(),
        )

    def _rozpocznij(self):
        if uruchom_automatyzacje is None:
            QMessageBox.warning(
                self,
                "Brak wymaganych składników",
                "Nie można uruchomić montażu, bo nie załadowano modułu montażu:\n"
                f"{BLAD_MONTAZU}\n\nSprawdź zakładkę Pomoc i doinstaluj brakujące elementy.",
            )
            self.tabs.setCurrentWidget(self.tab_pomoc)
            self._uruchom_test_systemu()
            return
        if not self._zapisz_zmienione_edytory():
            return
        konfiguracja = self._pobierz_konfiguracje()
        for key, label, kind in self.SCIEZKI:
            sciezka = getattr(konfiguracja, key)
            if kind == "dir" and not sciezka.is_dir():
                QMessageBox.warning(self, "Nieprawidłowa ścieżka", f"{label}: folder nie istnieje.\n{sciezka}")
                return
            if kind == "file" and not sciezka.is_file():
                QMessageBox.warning(self, "Nieprawidłowa ścieżka", f"{label}: plik nie istnieje.\n{sciezka}")
                return

        try:
            filmy = [
                plik for plik in konfiguracja.folder_wejsciowy.iterdir()
                if plik.suffix.lower() in {".mp4", ".mov"} and "TEMP_MPY_" not in plik.name.upper()
            ]
        except OSError as blad:
            QMessageBox.warning(self, "Błąd folderu", f"Nie można odczytać nagrań:\n{blad}")
            return
        if not filmy:
            QMessageBox.warning(self, "Brak nagrań", "Folder źródłowy nie zawiera filmów MP4 ani MOV.")
            return

        for key, _, _ in self.SCIEZKI:
            self.settings.setValue(key, str(getattr(konfiguracja, key)))
        self.log_view.clear()
        self.status.setText("Przygotowywanie montażu…")
        self.progress_bar.setRange(0, len(filmy))
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.job_complete = False

        self.cancel_event = Event()
        self.worker_thread = QThread(self)
        self.worker = MontazWorker(konfiguracja, self.cancel_event)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._dodaj_log)
        self.worker.progress.connect(self._aktualizuj_postep)
        self.worker.completed.connect(self._zakoncz)
        self.worker.completed.connect(self.worker_thread.quit)
        self.worker.completed.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._posprzataj_watek)
        self.worker_thread.start()

    def _przerwij(self):
        if self.cancel_event is None or self.cancel_event.is_set():
            return
        self.cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.status.setText("Przerywanie generowania…")
        self._dodaj_log("Żądanie przerwania wysłane. Trwa bezpieczne zatrzymywanie bieżącego etapu.")

    def _dodaj_log(self, tekst: str):
        self.log_view.appendPlainText(tekst)

    def _aktualizuj_postep(self, indeks: int, razem: int, nazwa: str, status: str):
        self.progress_bar.setRange(0, razem)
        self.progress_bar.setValue(indeks)
        etykiety = {
            "done": "gotowe",
            "error": "błąd",
            "skipped": "pominięto",
            "cancelled": "przerwano",
        }
        self.status.setText(f"{indeks}/{razem}: {nazwa} — {etykiety.get(status, status)}")

    def _zakoncz(self, sukces: bool, komunikat: str):
        self.job_complete = True
        if self.worker_thread is None:
            self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.cancel_event = None
        self.status.setText(komunikat)
        if sukces:
            self.progress_bar.setValue(self.progress_bar.maximum())
        if not sukces and "przerwano" not in komunikat.lower():
            QMessageBox.warning(self, "Montaż zakończony z błędem", komunikat)
        elif not sukces:
            self.log_view.append(komunikat)

    def _posprzataj_watek(self):
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
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IPSC Video Automato")
    window = MainWindow()
    window.show()
    QTimer.singleShot(300, window._test_przy_starcie)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
