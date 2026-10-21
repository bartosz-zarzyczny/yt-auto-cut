import importlib
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from typing import List

from app_settings import find_imagemagick
# (nazwa pakietu w pip, wymagana wersja)
LIBRARIES = (
    ("moviepy", "<2.0.0"),
    ("decorator", "==4.4.2"),
    ("numpy", ""),
    ("librosa", ""),
    ("scipy", ""),
    ("Pillow", ""),
    ("PySide6", ">=6.5,<7"),
    ("google-auth", ""),
    ("google-api-python-client", ""),
    ("google-auth-oauthlib", ""),
    ("google-auth-httplib2", ""),
    ("tzdata", ""),
)

IMAGEMAGICK_WINDOWS = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

# Sprzętowe kodeki H.264 w kolejności prób. AMF ma własne nazwy presetów (speed/balanced/quality).
HARDWARE_CODECS_WINDOWS_LINUX = ("h264_nvenc", "h264_amf", "h264_qsv")
HARDWARE_CODECS_MACOS = ("h264_videotoolbox",)
CODEC_DESCRIPTIONS = {
    "h264_nvenc": "NVIDIA NVENC",
    "h264_amf": "AMD AMF",
    "h264_qsv": "Intel Quick Sync",
    "h264_videotoolbox": "Apple VideoToolbox",
    "libx264": "procesor (libx264)",
}
CODEC_PRESETS = {"h264_amf": "speed"}
DEFAULT_PRESET = "fast"


def hardware_codecs():
    return HARDWARE_CODECS_MACOS if platform.system() == "Darwin" else HARDWARE_CODECS_WINDOWS_LINUX


def preset_for_codec(codec):
    return CODEC_PRESETS.get(codec, DEFAULT_PRESET)


def codec_works(ffmpeg, codec):
    """Próbne kodowanie z tymi samymi opcjami, których używa montaż (preset, pix_fmt)."""
    command = [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=0.2",
               "-c:v", codec, "-preset", preset_for_codec(codec), "-pix_fmt", "yuv420p",
               "-f", "null", "-"]
    try:
        return subprocess.run(command, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@dataclass
class CheckResult:
    name: str
    ok: bool
    version: str
    note: str = ""
    install_hint: str = ""


def _package_version(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _meets_requirement(version, requirement):
    if not requirement:
        return True
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
        return Version(version) in SpecifierSet(requirement)
    except Exception:
        return True


def _first_line(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30,
                                encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if text else ""


IMPORT_NAMES = {
    "moviepy": "moviepy.editor",
    "Pillow": "PIL",
    "google-auth": "google.auth",
    "google-api-python-client": "googleapiclient",
    "google-auth-oauthlib": "google_auth_oauthlib",
    "google-auth-httplib2": "google_auth_httplib2",
}


def _import_error(package):
    module = IMPORT_NAMES.get(package, package.replace("-", "_"))
    try:
        importlib.import_module(module)
    except Exception as error:
        return f"{type(error).__name__}: {error}"
    return None


def check_libraries() -> List[CheckResult]:
    results = []
    for name, requirement in LIBRARIES:
        version = _package_version(name)
        command = f'"{sys.executable}" -m pip install "{name}{requirement}"'
        if version is None:
            results.append(CheckResult(name, False, "brak", "Nie zainstalowano", command))
        elif not _meets_requirement(version, requirement):
            results.append(CheckResult(name, False, version, f"Wymagana wersja {requirement}", command))
        elif (error := _import_error(name)) is not None:
            results.append(CheckResult(name, False, version, f"Nie można zaimportować ({error})",
                                       command.replace("pip install", "pip install --force-reinstall")))
        else:
            results.append(CheckResult(name, True, version, f"wymagane {requirement}" if requirement else ""))
    return results


def _ffmpeg_instructions():
    system = platform.system()
    if system == "Darwin":
        return "Zainstaluj FFmpeg z libx264: brew install ffmpeg"
    if system == "Windows":
        return "Pobierz pełną wersję FFmpeg z https://www.gyan.dev/ffmpeg/builds/ i dodaj folder bin do PATH."
    return "Zainstaluj FFmpeg z libx264: sudo apt install ffmpeg"


def _imagemagick_instructions():
    system = platform.system()
    if system == "Darwin":
        return "Zainstaluj: brew install imagemagick"
    if system == "Windows":
        return ("Pobierz z https://imagemagick.org/script/download.php#windows i przy instalacji "
                "zaznacz 'Install legacy utilities (e.g. convert)' oraz dodanie do PATH.")
    return "Zainstaluj: sudo apt install imagemagick"


def _find_ffmpeg():
    """FFmpeg używany przez MoviePy (jeśli dostępny), w przeciwnym razie z PATH."""
    try:
        from moviepy.config import get_setting
        return get_setting("FFMPEG_BINARY")
    except Exception:
        return shutil.which("ffmpeg")


def check_software() -> List[CheckResult]:
    results = []
    ffmpeg = _find_ffmpeg()
    version = _first_line([ffmpeg, "-version"]) if ffmpeg else None
    if version is None:
        results.append(CheckResult("FFmpeg", False, "brak", "Nie znaleziono lub nie uruchamia się",
                                   _ffmpeg_instructions()))
        results.append(CheckResult("Kodek libx264", False, "brak", "Wymaga FFmpeg", _ffmpeg_instructions()))
    else:
        number = version.replace("ffmpeg version ", "").split()[0] if version else "nieznana"
        results.append(CheckResult("FFmpeg", True, number, ffmpeg))
        if codec_works(ffmpeg, "libx264"):
            results.append(CheckResult("Kodek libx264", True, "działa"))
        else:
            results.append(CheckResult("Kodek libx264", False, "brak", "FFmpeg bez libx264",
                                       _ffmpeg_instructions()))
        checked = [k for k in hardware_codecs()]
        working = [k for k in checked if codec_works(ffmpeg, k)]
        if working:
            results.append(CheckResult(
                "Kodek sprzętowy (opcjonalny)", True, working[0],
                f"{CODEC_DESCRIPTIONS.get(working[0], '')}; użyty zostanie pierwszy działający"))
        else:
            results.append(CheckResult(
                "Kodek sprzętowy (opcjonalny)", True, "niedostępny",
                f"Sprawdzono: {', '.join(checked)}. Montaż użyje libx264 (wolniej, ale działa wszędzie)"))

    path = find_imagemagick()
    if not path and platform.system() == "Windows" and os.path.isfile(IMAGEMAGICK_WINDOWS):
        path = IMAGEMAGICK_WINDOWS
    if not path:
        results.append(CheckResult("ImageMagick", False, "brak", "Potrzebny do napisów",
                                   _imagemagick_instructions()))
    else:
        version = " ".join((_first_line([path, "-version"]) or "nieznana").split()[:3])
        results.append(CheckResult("ImageMagick", True, version, path))
    return results


def run_system_check() -> List[CheckResult]:
    results = [CheckResult("Python", sys.version_info >= (3, 8), platform.python_version(),
                           f"{platform.system()} {platform.release()}",
                           "Zainstaluj Python 3.8 lub nowszy z python.org")]
    results.extend(check_libraries())
    results.extend(check_software())
    return results


def format_text(results: List[CheckResult]) -> str:
    lines = ["TEST SYSTEMU", ""]
    for w in results:
        lines.append(f"[{'OK' if w.ok else 'BRAK'}] {w.name}: {w.version}" + (f"  ({w.note})" if w.note else ""))
    missing = [w for w in results if not w.ok]
    lines.append("")
    if missing:
        lines.append("DO DOINSTALOWANIA / NAPRAWY:")
        lines.extend(f"  - {w.name}: {w.install_hint}" for w in missing)
        lines.append("")
        lines.append("Po instalacji uruchom aplikację ponownie.")
    else:
        lines.append("Wszystko gotowe do pracy.")
    return "\n".join(lines)


def show_report_without_qt():
    """Awaryjny raport, gdy nie da się uruchomić okna Qt (np. brak PySide6)."""
    text = format_text(run_system_check())
    try:
        import tkinter
        from tkinter import scrolledtext
        window = tkinter.Tk()
        window.title("IPSC Video Automato — brakujące składniki")
        window.geometry("900x560")
        field = scrolledtext.ScrolledText(window, font=("Consolas", 10), wrap="word")
        field.insert("1.0", "Nie można uruchomić interfejsu aplikacji.\n\n" + text)
        field.configure(state="disabled")
        field.pack(fill="both", expand=True)
        window.mainloop()
    except Exception:
        print(text)


def format_html(results: List[CheckResult]) -> str:
    def esc(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    rows = []
    for w in results:
        mark = "<span style='color:#43e0c1'>✔</span>" if w.ok else "<span style='color:#ff7b7b'>✘</span>"
        rows.append(
            f"<tr><td>{mark}</td><td><b>{esc(w.name)}</b></td><td>{esc(w.version)}</td>"
            f"<td style='color:#8998ac'>{esc(w.note)}</td></tr>"
        )
    missing = [w for w in results if not w.ok]
    html = ["<h2>Test systemu</h2><table cellspacing='0' cellpadding='4'>", *rows, "</table>"]
    if missing:
        html.append("<h3 style='color:#ff7b7b'>Do doinstalowania / naprawy</h3><ul>")
        for w in missing:
            html.append(f"<li><b>{esc(w.name)}</b>: <code>{esc(w.install_hint)}</code></li>")
        html.append("</ul>")
    else:
        html.append("<h3 style='color:#43e0c1'>Wszystko gotowe do pracy.</h3>")
    return "".join(html)
