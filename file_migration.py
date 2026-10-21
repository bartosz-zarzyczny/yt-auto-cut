"""Zmiana nazw plików tekstowych projektu (bez ciężkich importów)."""
from pathlib import Path

OLD_NAMES = {
    "wynik2.txt": "wyniki.txt",
    "tory.txt": "mapowanie_torow.txt",
    "dodatkowe_teksty.txt": "teksty_wideo.txt",
}


def move_old_files(directory):
    """Zmienia nazwy starych plików na nowe, o ile nowego jeszcze nie ma."""
    directory = Path(directory)
    for old, new in OLD_NAMES.items():
        old_file, new_file = directory / old, directory / new
        if old_file.exists() and not new_file.exists():
            try:
                old_file.rename(new_file)
            except OSError:
                pass


def fix_path(path):
    """Zapisaną w ustawieniach starą nazwę pliku zamienia na nową."""
    file = Path(str(path))
    new_name = OLD_NAMES.get(file.name.lower())
    return str(file.with_name(new_name)) if new_name else str(path)
