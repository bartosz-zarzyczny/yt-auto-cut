import argparse
import os
import random
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, List, Optional
from moviepy.editor import VideoFileClip, CompositeVideoClip, CompositeAudioClip, AudioFileClip
import moviepy.audio.fx.all as afx
from timer_detect import zglos_wykrycie_timera, znajdz_sygnaly_timera
from timer_trim import choose_trim_range, trim_video
from fast_trim import probe_duration, trim_copy
from additional_texts import create_text_clips
from text_render import text_clip
from logo_overlay import create_logo_clip
from track_order import RESOLUTIONS, DEFAULT_RESOLUTION
from track_mapping import assign_tracks
from file_migration import move_old_files
from app_settings import ensure_settings_file
from system_settings import PROJECT_DIR, choose_font, check_environment, preset_for_codec
from generate_names import generate_title, read_match_data, safe_file_name
from video_cancellation import CancellableProgressLogger, GenerationCancelled

# Pillow compatibility: some Pillow versions removed Image.ANTIALIAS constant.
# MoviePy (resize) expects Image.ANTIALIAS; provide a fallback mapping to Resampling.LANCZOS.
try:
    from PIL import Image as _PILImage
except Exception:
    _PILImage = None

if _PILImage is not None and not hasattr(_PILImage, 'ANTIALIAS'):
    if hasattr(_PILImage, 'Resampling') and hasattr(_PILImage.Resampling, 'LANCZOS'):
        _PILImage.ANTIALIAS = _PILImage.Resampling.LANCZOS
    elif hasattr(_PILImage, 'LANCZOS'):
        _PILImage.ANTIALIAS = _PILImage.LANCZOS

ensure_settings_file()

# ===================================================================
# KONFIGURACJA ŚCIEŻEK
# ===================================================================
FOLDER_WEJSCIOWY = os.path.join(PROJECT_DIR, "Surowe")
FOLDER_WYJSCIOWY = os.path.join(PROJECT_DIR, "Gotowe")
FOLDER_MUZYKI = os.path.join(PROJECT_DIR, "Muzyka")
PLIK_Z_WYNIKAMI = os.path.join(PROJECT_DIR, "wyniki.txt")
PLIK_Z_TEKSTAMI = os.path.join(PROJECT_DIR, "teksty_wideo.txt")
PLIK_Z_TORAMI = os.path.join(PROJECT_DIR, "mapowanie_torow.txt")
PLIK_OPISU_ZAWODOW = os.path.join(PROJECT_DIR, "opis_zawodow.txt")
BUFFER_LIST_FILE = Path(PROJECT_DIR) / "buffer.txt"
move_old_files(PROJECT_DIR)


from results_parser import TRYB_WYNIKOW_ECM, TRYB_WYNIKOW_PRACTISCORE, TRYB_WYNIKOW_TRENING  # noqa: E402

ACTION_RENDER = "render"
ACTION_SKIP_NO_RESULT = "skip_no_result"
ACTION_SKIP_EXISTS = "skip_exists"


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
    # Tylko przycięcie: bez muzyki, napisów, logo i zmiany rozdzielczości; obraz kopiowany bez ponownego kodowania.
    trim_only: bool = False
    # False = gotowy film o tej samej nazwie zostaje, a nagranie jest pomijane (bez ponownego renderu).
    overwrite_existing: bool = False


@dataclass(frozen=True)
class PlanItem:
    """Jedna pozycja planu montażu: co stanie się z danym nagraniem."""
    file_name: str
    track: str
    resolution: tuple
    result: Optional[dict]
    output_name: str
    output_exists: bool
    action: str  # "render", "skip_no_result", "skip_exists"
    timer_start: Optional[float] = None


@dataclass(frozen=True)
class PublishOptions:
    youtube_schedule: Optional[str] = None
    publish_now: bool = False
    unlisted: bool = False
    cloudflare: bool = False
    buffer: bool = False
    buffer_platforms: tuple = ()
    buffer_post_type: str = "reel"
    buffer_schedule: Optional[str] = None

# ===================================================================
# FUNKCJE POMOCNICZE
# ===================================================================

from results_parser import (  # noqa: E402,F401 — ponowny eksport dla zgodności
    CZYTNIKI_WYNIKOW,
    czytaj_wyniki_z_pliku,
)


# ===================================================================
# GŁÓWNA LOGIKA
# ===================================================================

VIDEO_EXTENSIONS = (".mp4", ".mov")
MUSIC_VOLUME = 0.12


def list_source_videos(folder) -> List[str]:
    """Nagrania MP4/MOV z folderu źródłowego (bez plików tymczasowych MoviePy), posortowane."""
    return sorted(
        name for name in os.listdir(folder)
        if name.lower().endswith(VIDEO_EXTENSIONS) and "TEMP_MPY_" not in name.upper()
    )


def _load_results(konfiguracja: KonfiguracjaSciezek) -> dict:
    if konfiguracja.dodaj_napisy or konfiguracja.plik_z_wynikami.is_file():
        return czytaj_wyniki_z_pliku(str(konfiguracja.plik_z_wynikami), konfiguracja.tryb_wynikow)
    return {}


def _names_available(description_file, report: Callable[[str], None]) -> bool:
    """Sprawdza opis zawodów raz, przed renderem, zamiast wykrywać błąd dopiero po zmontowaniu filmu."""
    try:
        read_match_data(Path(description_file))
    except (OSError, ValueError) as error:
        report(f"UWAGA: {error} Gotowe filmy zachowają nazwy techniczne (Gotowe_Stage_N.mp4).")
        return False
    return True


def _output_name(track, description_file, names_available: bool) -> str:
    technical_name = f"Gotowe_Stage_{track}.mp4"
    if not names_available:
        return technical_name
    return safe_file_name(generate_title(technical_name, Path(description_file)), ".mp4")


def plan_assembly(
    konfiguracja: Optional[KonfiguracjaSciezek] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    detect_timer: bool = False,
    cancel_event: Optional[Event] = None,
) -> List[PlanItem]:
    """Plan montażu bez renderowania: tor, wynik, nazwa wyjściowa i decyzja dla każdego nagrania.

    detect_timer=True dodatkowo analizuje dźwięk (wolniejsze), aby pokazać wykryty start przebiegu."""
    konfiguracja = konfiguracja or KonfiguracjaSciezek()
    report = log_callback or (lambda _text: None)
    results = _load_results(konfiguracja)
    names_available = _names_available(konfiguracja.plik_opisu_zawodow, report)
    assigned = assign_tracks(
        list_source_videos(konfiguracja.folder_wejsciowy),
        str(konfiguracja.plik_z_torami),
        RESOLUTIONS.get(konfiguracja.domyslna_orientacja, DEFAULT_RESOLUTION),
    )
    plan = []
    for file_name, track, resolution in assigned:
        result = results.get(track)
        output_name = _output_name(track, konfiguracja.plik_opisu_zawodow, names_available)
        output_exists = (Path(konfiguracja.folder_wyjsciowy) / output_name).is_file()
        if result is None and konfiguracja.dodaj_napisy and not konfiguracja.trim_only:
            action = ACTION_SKIP_NO_RESULT
        elif output_exists and not konfiguracja.overwrite_existing:
            action = ACTION_SKIP_EXISTS
        else:
            action = ACTION_RENDER
        timer_start = None
        if detect_timer and action == ACTION_RENDER:
            if cancel_event and cancel_event.is_set():
                raise GenerationCancelled("Generowanie przerwano przez użytkownika.")
            try:
                signals = znajdz_sygnaly_timera(
                    os.path.join(konfiguracja.folder_wejsciowy, file_name), cancel_event
                )
            except GenerationCancelled:
                raise
            except Exception as error:
                report(f"[TIMER] {file_name}: nie udało się przeanalizować dźwięku: {error}")
                signals = []
            timer_start = signals[0][0] if signals else None
        plan.append(PlanItem(
            file_name, track, resolution, result, output_name, output_exists, action, timer_start
        ))
    return plan


def _music_files(konfiguracja: KonfiguracjaSciezek) -> List[str]:
    if konfiguracja.trim_only or not konfiguracja.add_music:
        return []
    if not os.path.isdir(konfiguracja.folder_muzyki):
        return []
    return [m for m in os.listdir(konfiguracja.folder_muzyki) if m.lower().endswith('.mp3')]


def uruchom_automatyzacje(
    yt=False,
    publikuj=False,
    konfiguracja: Optional[KonfiguracjaSciezek] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    cancel_event: Optional[Event] = None,
    publish_options: Optional[PublishOptions] = None,
    render_progress_callback: Optional[Callable[[float], None]] = None,
):
    """progress_callback(indeks, liczba, plik, status): status "started" na początku filmu, potem wynik.
    render_progress_callback(ułamek 0..1): postęp renderowania bieżącego filmu."""
    konfiguracja = konfiguracja or KonfiguracjaSciezek()
    options = publish_options or PublishOptions()

    def raportuj(tekst):
        print(tekst)
        if log_callback:
            log_callback(tekst)

    def sprawdz_przerwanie():
        if cancel_event and cancel_event.is_set():
            raise GenerationCancelled("Generowanie przerwano przez użytkownika.")

    srodowisko_ok, kodek = check_environment(raportuj)
    if not srodowisko_ok:
        raportuj("Nie można rozpocząć montażu: sprawdź wymagane narzędzia systemowe.")
        return False

    os.makedirs(konfiguracja.folder_wyjsciowy, exist_ok=True)
    if konfiguracja.trim_only:
        raportuj("Tryb: tylko przycięcie (bez muzyki, napisów i logo; obraz bez ponownego kodowania).")

    plan = plan_assembly(konfiguracja, raportuj)
    muzyka_pliki = _music_files(konfiguracja)
    if not plan:
        raportuj(f"Nie znaleziono filmów MP4/MOV w folderze: {konfiguracja.folder_wejsciowy}")

    liczba_bledow = 0
    przerwano = False
    total = len(plan)
    for indeks, item in enumerate(plan, start=1):
        nazwa_pliku, nr_toru, rozdzielczosc = item.file_name, item.track, item.resolution
        if cancel_event and cancel_event.is_set():
            przerwano = True
            raportuj("Generowanie przerwano przez użytkownika.")
            if progress_callback:
                progress_callback(indeks, total, nazwa_pliku, "cancelled")
            break

        raportuj(f"\n>>> Przetwarzanie: {nazwa_pliku} jako TOR {nr_toru}")

        if item.action == ACTION_SKIP_NO_RESULT:
            raportuj(f"Pominięto {nazwa_pliku}: brak wyników dla toru {nr_toru}.")
            if progress_callback:
                progress_callback(indeks, total, nazwa_pliku, "skipped")
            continue
        if item.action == ACTION_SKIP_EXISTS:
            raportuj(
                f"Pominięto {nazwa_pliku}: gotowy film już istnieje ({item.output_name}). "
                "Włącz nadpisywanie, aby zmontować go ponownie."
            )
            if progress_callback:
                progress_callback(indeks, total, nazwa_pliku, "exists")
            continue

        if progress_callback:
            progress_callback(indeks, total, nazwa_pliku, "started")
        dane = item.result
        czas_przebiegu = dane["czas"] if dane else None

        sciezka_wej = os.path.join(konfiguracja.folder_wejsciowy, nazwa_pliku)
        sciezka_wyj = Path(konfiguracja.folder_wyjsciowy) / item.output_name
        sciezka_tymczasowa = sciezka_wyj.with_name(
            f"Gotowe_Stage_{nr_toru}_TEMP_MPY_{uuid.uuid4().hex}.mp4"
        )
        sciezka_audio_tymczasowego = sciezka_tymczasowa.with_name(
            f"{sciezka_tymczasowa.stem}_TEMP_AUDIO.m4a"
        )
        video = None
        wideo_koncowe = None
        audio_muzyka = None

        try:
            sprawdz_przerwanie()
            sygnaly = zglos_wykrycie_timera(sciezka_wej, raportuj, cancel_event)
            sprawdz_przerwanie()

            if konfiguracja.trim_only:
                zakres = choose_trim_range(sygnaly, czas_przebiegu, probe_duration(sciezka_wej), raportuj)
                raportuj("Przycinanie (kopiowanie obrazu bez ponownego kodowania)...")
                trim_copy(sciezka_wej, sciezka_tymczasowa, zakres, cancel_event)
            else:
                video = VideoFileClip(sciezka_wej)
                sprawdz_przerwanie()
                video = trim_video(video, sygnaly, czas_przebiegu, raportuj)

                nowy_czas_trwania = video.duration
                raportuj(f"Czas wideo: {nowy_czas_trwania:.2f}s")

                # --- MUZYKA ---
                if muzyka_pliki:
                    losowy_utwor = random.choice(muzyka_pliki)
                    sciezka_muzyki = os.path.join(konfiguracja.folder_muzyki, losowy_utwor)

                    audio_muzyka = AudioFileClip(sciezka_muzyki)
                    audio_muzyka = afx.audio_loop(audio_muzyka, duration=nowy_czas_trwania)

                    if hasattr(audio_muzyka, 'volx'):
                        audio_muzyka = audio_muzyka.volx(MUSIC_VOLUME)
                    elif hasattr(audio_muzyka, 'multiply_volume'):
                        audio_muzyka = audio_muzyka.multiply_volume(MUSIC_VOLUME)
                    else:
                        audio_muzyka = audio_muzyka.fl(lambda gf, t: MUSIC_VOLUME * gf(t), keep_duration=True)

                    audio_muzyka = audio_muzyka.fx(afx.audio_fadeout, 1.0)

                    ziksowane_audio = CompositeAudioClip([video.audio, audio_muzyka]).set_fps(44100)
                    video = video.set_audio(ziksowane_audio)

                # --- NAPISY ---
                warstwy_napisow = []
                if konfiguracja.dodaj_napisy and dane:
                    tekst_wyswietlany = (f"STAGE {nr_toru} | Miejsce: {dane['miejsce']} ({dane['procent']})\n"
                                         f"Czas: {dane['czas']}s | HF: {dane['hf']} | Pkt: {dane['punkty']}")

                    napis = text_clip(
                        tekst_wyswietlany, nowy_czas_trwania, font_path=choose_font(), font_size=55,
                        color="white", stroke_color="black", stroke_width=2.5,
                    )

                    # Napis wyrównany do dołu
                    napis = napis.set_position(('center', 0.85), relative=True)
                    warstwy_napisow = [napis]

                # --- ZMIANA ROZDZIELCZOŚCI (H = 1920x1080, V/domyślnie = 1080x1920) ---
                video = video.resize(newsize=rozdzielczosc)
                # Tworzymy Composite z jawnie ustawionym rozmiarem wyjściowym, aby napisy i pozycjonowanie działały poprawnie
                if konfiguracja.add_video_texts:
                    warstwy_napisow += create_text_clips(
                        str(konfiguracja.plik_z_tekstami), nowy_czas_trwania, raportuj
                    )
                klip_logo = create_logo_clip(konfiguracja.plik_logo, nowy_czas_trwania, rozdzielczosc[0], raportuj)
                if klip_logo is not None:
                    warstwy_napisow.append(klip_logo)
                wideo_koncowe = CompositeVideoClip([video, *warstwy_napisow], size=rozdzielczosc).set_fps(30)
                sprawdz_przerwanie()

                # --- RENDEROWANIE Z ZACHOWANIEM KOLORÓW I BEZ OBROTÓW ---
                raportuj(f"Rozpoczynam renderowanie ({kodek})...")
                wideo_koncowe.write_videofile(
                    str(sciezka_tymczasowa),
                    fps=30,
                    codec=kodek,
                    audio_codec="aac",
                    bitrate="8000k",
                    preset=preset_for_codec(kodek),
                    ffmpeg_params=['-pix_fmt', 'yuv420p'],  # Gwarantuje poprawne kolory i odtwarzanie w Windows
                    temp_audiofile=str(sciezka_audio_tymczasowego),
                    logger=CancellableProgressLogger(cancel_event or Event(), render_progress_callback),
                )

            sprawdz_przerwanie()
            os.replace(sciezka_tymczasowa, sciezka_wyj)
            raportuj(f"Zapisano: {sciezka_wyj.name}")
            raportuj("Zakończono sukcesem!\n")
            if progress_callback:
                progress_callback(indeks, total, nazwa_pliku, "done")

        except GenerationCancelled:
            przerwano = True
            raportuj("Generowanie przerwano przez użytkownika.")
            if progress_callback:
                progress_callback(indeks, total, nazwa_pliku, "cancelled")
            break
        except Exception as e:
            liczba_bledow += 1
            raportuj(f"BŁĄD podczas przetwarzania: {str(e)}\n")
            if progress_callback:
                progress_callback(indeks, total, nazwa_pliku, "error")
        finally:
            for klip in (wideo_koncowe, video, audio_muzyka):
                if klip is not None:
                    klip.close()
            for plik_tymczasowy in (sciezka_tymczasowa, sciezka_audio_tymczasowego):
                try:
                    plik_tymczasowy.unlink()
                except FileNotFoundError:
                    pass

    if options.cloudflare and not przerwano:
        from cloudflare_upload import upload_to_configured_bucket

        liczba_bledow += upload_to_configured_bucket(konfiguracja.folder_wyjsciowy, BUFFER_LIST_FILE, raportuj)

    if options.buffer and not przerwano:
        from buffer_upload import create_buffer_drafts

        liczba_bledow += create_buffer_drafts(
            BUFFER_LIST_FILE,
            list(options.buffer_platforms),
            options.buffer_post_type,
            options.buffer_schedule,
            konfiguracja.plik_opisu_zawodow,
            raportuj,
        )

    if yt and not przerwano:
        from youtube_upload import main as uruchom_youtube

        argumenty_youtube = [str(konfiguracja.folder_wyjsciowy)]
        if publikuj:
            argumenty_youtube.append("--publish")
        if options.youtube_schedule:
            argumenty_youtube += ["--schedule", options.youtube_schedule]
        if options.publish_now:
            argumenty_youtube.append("--publish-now")
        if options.unlisted:
            argumenty_youtube.append("--unlisted")
        uruchom_youtube(argumenty_youtube)
    return bool(plan) and liczba_bledow == 0 and not przerwano


def main():
    parser = argparse.ArgumentParser(
        description="Montuje nagrania IPSC, a opcjonalnie przygotowuje publikację YouTube.",
        prefix_chars="-/",
    )
    parser.add_argument(
        "--yt",
        "/yt",
        dest="yt",
        action="store_true",
        help="Po montażu uruchamia podgląd kolejki YouTube (bez wysyłania).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Wysyła filmy do YouTube; wymaga jednocześnie opcji --yt lub /yt.",
    )
    schedule_group = parser.add_mutually_exclusive_group()
    schedule_group.add_argument(
        "--schedule",
        metavar="HARMONOGRAM",
        help="Harmonogram publikacji YouTube, np. 'pon=07:30,sob=10:00' (wymaga --yt i --publish).",
    )
    schedule_group.add_argument(
        "--publish-now",
        dest="publish_now",
        action="store_true",
        help="Publikuje filmy na YouTube od razu, bez harmonogramu (wymaga --yt i --publish).",
    )
    parser.add_argument(
        "--unlisted",
        action="store_true",
        help="Dodatkowo wysyła na YouTube wersję unlisted z linkiem youtu.be (wymaga --yt i --publish).",
    )
    parser.add_argument(
        "--cloudflare",
        action="store_true",
        help="Po montażu wysyła MP4 z folderu Gotowe na Cloudflare R2 i dopisuje linki do buffer.txt.",
    )
    parser.add_argument(
        "--buffer",
        action="store_true",
        help="Po montażu tworzy szkice w Buffer z linków z buffer.txt (wymaga --buffer-platforms).",
    )
    parser.add_argument(
        "--buffer-platforms",
        metavar="PLATFORMY",
        help="Platformy Buffer oddzielone przecinkami: facebook,instagram,x (wymaga --buffer).",
    )
    parser.add_argument(
        "--buffer-post-type",
        metavar="TYP",
        default="reel",
        choices=["reel", "post", "story"],
        help="Typ posta dla Facebook/Instagram w Buffer (domyślnie: reel).",
    )
    parser.add_argument(
        "--buffer-schedule",
        metavar="HARMONOGRAM",
        help="Harmonogram szkiców Buffer w formacie 'pon=07:30,sob=10:00' (wymaga --buffer).",
    )
    args = parser.parse_args()

    from youtube_upload import parse_schedule
    from buffer_upload import parse_platforms

    publish_flags_used = args.publish or args.schedule or args.publish_now or args.unlisted
    if publish_flags_used and not args.yt:
        parser.error("--publish, --schedule, --publish-now i --unlisted wymagają opcji --yt lub /yt.")
    if args.publish and not args.yt:
        parser.error("--publish wymaga również opcji --yt lub /yt.")
    if args.buffer_platforms and not args.buffer:
        parser.error("--buffer-platforms wymaga opcji --buffer.")
    if args.buffer_schedule and not args.buffer:
        parser.error("--buffer-schedule wymaga opcji --buffer.")
    if args.buffer and not args.buffer_platforms:
        parser.error("--buffer wymaga opcji --buffer-platforms, np. --buffer-platforms facebook,instagram.")
    if args.schedule:
        try:
            parse_schedule(args.schedule)
        except ValueError as error:
            parser.error(f"--schedule: {error}")
    if args.buffer_schedule:
        try:
            parse_schedule(args.buffer_schedule)
        except ValueError as error:
            parser.error(f"--buffer-schedule: {error}")
    buffer_platforms: tuple = ()
    if args.buffer_platforms:
        try:
            buffer_platforms = tuple(parse_platforms(args.buffer_platforms))
        except ValueError as error:
            parser.error(f"--buffer-platforms: {error}")

    options = PublishOptions(
        youtube_schedule=args.schedule,
        publish_now=args.publish_now,
        unlisted=args.unlisted,
        cloudflare=args.cloudflare,
        buffer=args.buffer,
        buffer_platforms=buffer_platforms,
        buffer_post_type=args.buffer_post_type,
        buffer_schedule=args.buffer_schedule,
    )
    ok = uruchom_automatyzacje(yt=args.yt, publikuj=args.publish, publish_options=options)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()