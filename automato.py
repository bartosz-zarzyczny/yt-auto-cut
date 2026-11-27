"""IPSC Video Automato z terminala: plan, montaż i publikacja jako osobne komendy.

Przykłady:
    python automato.py check
    python automato.py plan --detect-timer
    python automato.py render --trim-only
    python automato.py render --no-music --overwrite
    python automato.py publish youtube            (podgląd, bez wysyłania)
    python automato.py publish youtube --publish --schedule "pon=07:30,sob=10:00"
    python automato.py publish cloudflare
    python automato.py publish buffer --platforms facebook,instagram

Montaż (render) nigdy niczego nie publikuje — publikacja to zawsze osobna komenda.
"""
import argparse
import json
import signal
import sys
from pathlib import Path
from threading import Event
from typing import List, Optional

from video_cancellation import GenerationCancelled

PROJECT_DIR = Path(__file__).resolve().parent

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_USAGE = 2
EXIT_CANCELLED = 130

RESULTS_MODES = ("practiscore", "ecm", "trening")
ACTION_LABELS = {
    "render": "do montażu",
    "skip_no_result": "pominięty: brak wyniku",
    "skip_exists": "pominięty: już istnieje",
}


def _add_project_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("ścieżki i ustawienia projektu")
    group.add_argument("--input", type=Path, default=PROJECT_DIR / "Surowe", help="Folder z nagraniami MP4/MOV.")
    group.add_argument("--output", type=Path, default=PROJECT_DIR / "Gotowe", help="Folder na gotowe filmy.")
    group.add_argument("--music", type=Path, default=PROJECT_DIR / "Muzyka", help="Folder z muzyką MP3.")
    group.add_argument("--results", type=Path, default=PROJECT_DIR / "wyniki.txt", help="Plik z wynikami.")
    group.add_argument("--results-mode", choices=RESULTS_MODES, default="practiscore", help="Format wyników.")
    group.add_argument("--tracks", type=Path, default=PROJECT_DIR / "mapowanie_torow.txt",
                       help="Plik z kolejnością torów.")
    group.add_argument("--texts", type=Path, default=PROJECT_DIR / "teksty_wideo.txt", help="Plik z tekstami wideo.")
    group.add_argument("--description", type=Path, default=PROJECT_DIR / "opis_zawodow.txt",
                       help="Plik z opisem zawodów (nazwy plików i tytuły).")
    group.add_argument("--orientation", choices=("V", "H"), default="V",
                       help="Domyślna orientacja: V = pionowe 1080x1920, H = poziome 1920x1080.")
    group.add_argument("--logo", default="", help="Plik logo (puste = bez logo).")
    group.add_argument("--no-results", action="store_true",
                       help="Bez planszy wyników; nagrania bez wyniku nie są pomijane.")
    group.add_argument("--overwrite", action="store_true",
                       help="Montuje ponownie także filmy, które już są w folderze wyjściowym.")
    group.add_argument("--trim-only", action="store_true",
                       help="Tylko przycięcie: bez muzyki, napisów i logo, obraz bez ponownego kodowania (szybko).")


def _add_render_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("elementy montażu")
    group.add_argument("--no-music", action="store_true", help="Bez podkładu muzycznego.")
    group.add_argument("--no-texts", action="store_true", help="Bez tekstów wideo u góry filmu.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="automato",
        description="IPSC Video Automato: przycinanie, montaż i publikacja nagrań z zawodów.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Kody wyjścia: 0 = sukces, 1 = błędy, 2 = złe argumenty, 130 = przerwano (Ctrl+C).",
    )
    commands = parser.add_subparsers(dest="command", metavar="KOMENDA", required=True)

    commands.add_parser("check", help="Sprawdza biblioteki, FFmpeg i kodeki wideo.")

    plan = commands.add_parser("plan", help="Pokazuje, co zostanie zmontowane (bez renderowania).")
    _add_project_arguments(plan)
    plan.add_argument("--detect-timer", action="store_true", help="Analizuje dźwięk i pokazuje start timera.")
    plan.add_argument("--json", action="store_true", help="Wynik w formacie JSON (dla skryptów).")

    render = commands.add_parser("render", help="Montuje lub tylko przycina nagrania (bez publikacji).")
    _add_project_arguments(render)
    _add_render_arguments(render)

    publish = commands.add_parser("publish", help="Publikuje gotowe filmy (osobno od montażu).")
    targets = publish.add_subparsers(dest="target", metavar="CEL", required=True)

    youtube = targets.add_parser("youtube", help="YouTube: domyślnie tylko podgląd kolejki.")
    youtube.add_argument("--folder", type=Path, default=PROJECT_DIR / "Gotowe", help="Folder lub plik MP4.")
    youtube.add_argument("--publish", action="store_true", help="Naprawdę wysyła filmy (bez tego: podgląd).")
    when = youtube.add_mutually_exclusive_group()
    when.add_argument("--schedule", help="Harmonogram, np. 'pon=07:30,sob=10:00'.")
    when.add_argument("--publish-now", action="store_true", help="Publikuje od razu, bez harmonogramu.")
    youtube.add_argument("--unlisted", action="store_true", help="Dodatkowo wersja niepubliczna (z linkiem).")
    youtube.add_argument("--description", type=Path, default=PROJECT_DIR / "opis_zawodow.txt")
    youtube.add_argument("--client-secrets", type=Path, help="Inny plik OAuth (client secret) z Google Cloud.")

    cloudflare = targets.add_parser("cloudflare", help="Wysyła MP4 do Cloudflare R2 i dopisuje linki do listy.")
    cloudflare.add_argument("--folder", type=Path, default=PROJECT_DIR / "Gotowe")
    cloudflare.add_argument("--list", type=Path, default=PROJECT_DIR / "buffer.txt", help="Lista linków Buffer.")

    buffer = targets.add_parser("buffer", help="Tworzy szkice postów w Buffer z linków z listy.")
    buffer.add_argument("--platforms", required=True, help="Np. facebook,instagram,x")
    buffer.add_argument("--post-type", choices=("reel", "post", "story"), default="reel")
    buffer.add_argument("--schedule", help="Harmonogram, np. 'pon=07:30,sob=10:00'.")
    buffer.add_argument("--list", type=Path, default=PROJECT_DIR / "buffer.txt", help="Lista linków Buffer.")
    buffer.add_argument("--description", type=Path, default=PROJECT_DIR / "opis_zawodow.txt")
    return parser


def build_config(args):
    """Konfiguracja montażu z argumentów (importuje moduł montażu dopiero tutaj — --help działa bez MoviePy)."""
    from ipsc_automato import KonfiguracjaSciezek

    return KonfiguracjaSciezek(
        folder_wejsciowy=args.input,
        folder_wyjsciowy=args.output,
        folder_muzyki=args.music,
        plik_z_wynikami=args.results,
        plik_z_tekstami=args.texts,
        plik_z_torami=args.tracks,
        plik_opisu_zawodow=args.description,
        domyslna_orientacja=args.orientation,
        dodaj_napisy=not args.no_results,
        plik_logo=args.logo,
        tryb_wynikow=args.results_mode,
        add_video_texts=not getattr(args, "no_texts", False),
        add_music=not getattr(args, "no_music", False),
        trim_only=args.trim_only,
        overwrite_existing=args.overwrite,
    )


def _install_ctrl_c(cancel_event: Event) -> None:
    """Pierwsze Ctrl+C prosi o bezpieczne przerwanie, drugie kończy program natychmiast."""
    def handler(_signum, _frame):
        if cancel_event.is_set():
            raise KeyboardInterrupt
        cancel_event.set()
        print("\nPrzerywanie po bieżącym etapie… (ponowne Ctrl+C kończy natychmiast)", file=sys.stderr)

    signal.signal(signal.SIGINT, handler)


def command_check(_args) -> int:
    from system_check import format_text, run_system_check

    results = run_system_check()
    print(format_text(results))
    return EXIT_ERRORS if any(not result.ok for result in results) else EXIT_OK


def _plan_rows(plan) -> List[dict]:
    return [
        {
            "file": item.file_name,
            "track": item.track,
            "orientation": "H" if item.resolution[0] > item.resolution[1] else "V",
            "time": item.result["czas"] if item.result else None,
            "output": item.output_name,
            "action": item.action,
            "timer_start": item.timer_start,
        }
        for item in plan
    ]


def command_plan(args) -> int:
    from ipsc_automato import plan_assembly

    cancel_event = Event()
    _install_ctrl_c(cancel_event)
    log = (lambda text: print(text, file=sys.stderr)) if args.json else print
    plan = plan_assembly(build_config(args), log, detect_timer=args.detect_timer, cancel_event=cancel_event)
    rows = _plan_rows(plan)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return EXIT_OK
    if not rows:
        print(f"Brak nagrań MP4/MOV w folderze: {args.input}")
        return EXIT_ERRORS
    print(f"{'Plik':<28} {'Tor':>4} {'H/V':>3} {'Czas':>8} {'Timer':>8}  Decyzja → plik wyjściowy")
    for row in rows:
        time_text = f"{row['time']:.2f}s" if row["time"] is not None else "—"
        if row["timer_start"] is not None:
            timer_text = f"{row['timer_start']:.2f}s"
        else:
            timer_text = "brak" if args.detect_timer and row["action"] == "render" else "—"
        print(f"{row['file'][:28]:<28} {row['track']:>4} {row['orientation']:>3} {time_text:>8} {timer_text:>8}"
              f"  {ACTION_LABELS[row['action']]} → {row['output']}")
    to_render = sum(1 for row in rows if row["action"] == "render")
    print(f"\nDo montażu: {to_render} z {len(rows)}.")
    return EXIT_OK


def command_render(args) -> int:
    from ipsc_automato import uruchom_automatyzacje

    cancel_event = Event()
    _install_ctrl_c(cancel_event)
    ok = uruchom_automatyzacje(konfiguracja=build_config(args), cancel_event=cancel_event)
    if cancel_event.is_set():
        return EXIT_CANCELLED
    return EXIT_OK if ok else EXIT_ERRORS


def command_publish(args) -> int:
    if args.target == "youtube":
        import youtube_upload

        argv = [str(args.folder), "--opis", str(args.description)]
        if args.publish:
            argv.append("--publish")
        if args.schedule:
            argv += ["--schedule", args.schedule]
        if args.publish_now:
            argv.append("--publish-now")
        if args.unlisted:
            argv.append("--unlisted")
        if args.client_secrets:
            argv += ["--client-secrets", str(args.client_secrets)]
        youtube_upload.main(argv)
        return EXIT_OK
    if args.target == "cloudflare":
        from cloudflare_upload import upload_to_configured_bucket

        return EXIT_ERRORS if upload_to_configured_bucket(args.folder, args.list, print) else EXIT_OK
    from buffer_upload import create_buffer_drafts, parse_platforms

    platforms = parse_platforms(args.platforms)
    errors = create_buffer_drafts(args.list, platforms, args.post_type, args.schedule, args.description, print)
    return EXIT_ERRORS if errors else EXIT_OK


COMMANDS = {
    "check": command_check,
    "plan": command_plan,
    "render": command_render,
    "publish": command_publish,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "render" and args.trim_only and (args.no_music or args.no_texts):
        print("Uwaga: --trim-only i tak pomija muzykę i teksty.", file=sys.stderr)
    try:
        return COMMANDS[args.command](args)
    except (KeyboardInterrupt, GenerationCancelled):
        print("\nPrzerwano.", file=sys.stderr)
        return EXIT_CANCELLED
    except (OSError, ValueError, RuntimeError) as error:
        print(f"BŁĄD: {error}", file=sys.stderr)
        return EXIT_ERRORS


if __name__ == "__main__":
    sys.exit(main())
