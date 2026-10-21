from track_order import read_track_order, DEFAULT_RESOLUTION


def assign_tracks(video_files, track_order_path, default_resolution=DEFAULT_RESOLUTION):
    """Zwraca listę (nazwa_pliku, nr_toru, rozdzielczosc). Gdy brak pliku lub wpisu w mapowanie_torow.txt,
    używa numeru wynikającego z pozycji w sortowaniu. Plik bez litery H/V dostaje rozdzielczość domyślną."""
    order = read_track_order(track_order_path, default_resolution)
    result = []
    for index, name in enumerate(sorted(video_files)):
        if index < len(order):
            track_no, resolution = order[index]
        else:
            track_no, resolution = str(index + 1), default_resolution
        result.append((name, track_no, resolution))
    return result
