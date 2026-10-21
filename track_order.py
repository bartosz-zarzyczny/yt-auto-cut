import os

DEFAULT_RESOLUTION = (1080, 1920)
RESOLUTIONS = {"H": (1920, 1080), "V": (1080, 1920)}


def read_track_order(file_path, default=DEFAULT_RESOLUTION):
    """Zwraca listę (nr_toru, (szer, wys)) w kolejności z mapowanie_torow.txt.
    Format linii: "numer" lub "numer;H" / "numer;V". Bez litery używana jest rozdzielczość `domyslna`."""
    if not os.path.exists(file_path):
        print(f"Brak pliku z kolejnością torów: {file_path}")
        return []

    result = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            track_no, _, orientation = line.partition(";")
            resolution = RESOLUTIONS.get(orientation.strip().upper(), default)
            result.append((track_no.strip(), resolution))
    return result
