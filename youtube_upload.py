import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from moviepy.editor import VideoFileClip

from generuj_nazwy import (
    KATALOG_PROJEKTU,
    PLIK_OPISU,
    generuj_opis_i_hashtagi,
    generuj_tytul,
    przemianuj_plik,
)

STREFA_CZASOWA = ZoneInfo("Europe/Warsaw")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
PLIK_CLIENT_SECRETS = KATALOG_PROJEKTU / "youtube_client_secret.json"
PLIK_TOKENU = KATALOG_PROJEKTU / "youtube_token.json"
PLIK_STANU = KATALOG_PROJEKTU / "youtube_upload_state.json"
YOUTUBE_CATEGORY_SPORTS = "17"
MAKS_CZAS_SHORTS_SEKUND = 180


@dataclass(frozen=True)
class FilmWKolejce:
    video_id: str
    tytul: str
    termin: Optional[datetime]


def najblizszy_wolny_termin(
    zajete_daty: Set[date], teraz: Optional[datetime] = None
) -> datetime:
    teraz = teraz or datetime.now(STREFA_CZASOWA)
    if teraz.tzinfo is None:
        raise ValueError("Bieżący czas musi zawierać informację o strefie czasowej.")
    teraz = teraz.astimezone(STREFA_CZASOWA)
    dzien = teraz.date()
    while True:
        godzina = time(10, 0) if dzien.weekday() >= 5 else time(7, 30)
        termin = datetime.combine(dzien, godzina, tzinfo=STREFA_CZASOWA)
        if dzien not in zajete_daty and termin > teraz:
            return termin
        dzien += timedelta(days=1)


def _autoryzuj(client_secrets: Path, token_file: Path) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as blad:
        raise RuntimeError(
            "Brak bibliotek Google API. Zainstaluj zależności: "
            "python -m pip install -r requirements.txt"
        ) from blad

    if not client_secrets.is_file():
        raise FileNotFoundError(
            f"Brak pliku OAuth {client_secrets}. Pobierz dane klienta OAuth typu "
            "'Aplikacja komputerowa' z Google Cloud i zapisz je pod tą nazwą."
        )

    credentials = None
    if token_file.is_file():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid or not credentials.has_scopes(SCOPES):
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
        credentials = flow.run_local_server(port=0)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=credentials)


def _wybierz_kanal(
    youtube: Any, channel_id: Optional[str]
) -> Dict[str, Any]:
    odpowiedz = youtube.channels().list(part="id,snippet,contentDetails", mine=True).execute()
    kanaly = odpowiedz.get("items", [])
    if channel_id:
        kanaly = [kanal for kanal in kanaly if kanal.get("id") == channel_id]
        if not kanaly:
            raise ValueError(
                f"Konto OAuth nie zwróciło wskazanego kanału YouTube: {channel_id}"
            )
    if len(kanaly) != 1:
        nazwy = ", ".join(
            f"{kanal.get('snippet', {}).get('title', 'bez nazwy')} ({kanal.get('id')})"
            for kanal in kanaly
        ) or "brak kanałów"
        raise ValueError(
            f"Nie można jednoznacznie wybrać kanału ({nazwy}). "
            "Ustaw zmienną YOUTUBE_CHANNEL_ID na ID właściwego kanału."
        )
    return kanaly[0]


def pobierz_kolejke(
    youtube: Any, kanal: Dict[str, Any]
) -> Tuple[Set[date], List[FilmWKolejce], Set[str]]:
    uploads_id = kanal["contentDetails"]["relatedPlaylists"]["uploads"]
    video_ids: List[str] = []
    page_token = None
    while True:
        odpowiedz = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()
        video_ids.extend(
            element["contentDetails"]["videoId"]
            for element in odpowiedz.get("items", [])
            if element.get("contentDetails", {}).get("videoId")
        )
        page_token = odpowiedz.get("nextPageToken")
        if not page_token:
            break

    zajete_daty: Set[date] = set()
    zaplanowane: List[FilmWKolejce] = []
    istniejace_tytuly: Set[str] = set()
    for poczatek in range(0, len(video_ids), 50):
        odpowiedz = youtube.videos().list(
            part="snippet,status",
            id=",".join(video_ids[poczatek:poczatek + 50]),
            maxResults=50,
        ).execute()
        for film in odpowiedz.get("items", []):
            tytul = film.get("snippet", {}).get("title", "")
            if tytul:
                istniejace_tytuly.add(tytul.casefold())
            status = film.get("status", {})
            publish_at = status.get("publishAt")
            termin = None
            if publish_at:
                termin = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
                if termin.tzinfo is None:
                    raise ValueError(f"Nieprawidłowy termin publikacji z API: {publish_at}")
                termin = termin.astimezone(STREFA_CZASOWA)
                zajete_daty.add(termin.date())
                zaplanowane.append(FilmWKolejce(film["id"], tytul, termin))
            elif status.get("privacyStatus") in {"public", "unlisted"}:
                published_at = film.get("snippet", {}).get("publishedAt")
                if published_at:
                    opublikowano = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    ).astimezone(STREFA_CZASOWA)
                    zajete_daty.add(opublikowano.date())
    zaplanowane.sort(key=lambda film: film.termin or datetime.max.replace(tzinfo=STREFA_CZASOWA))
    return zajete_daty, zaplanowane, istniejace_tytuly


def _skrot_jest_poprawny(sciezka: Path) -> None:
    clip = VideoFileClip(str(sciezka))
    try:
        if clip.duration is None or clip.duration > MAKS_CZAS_SHORTS_SEKUND:
            raise ValueError(
                f"{sciezka.name}: Shorts muszą mieć maksymalnie "
                f"{MAKS_CZAS_SHORTS_SEKUND} sekund."
            )
        if clip.h < clip.w:
            raise ValueError(
                f"{sciezka.name}: Short musi mieć format pionowy lub kwadratowy "
                f"(plik ma {clip.w}x{clip.h})."
            )
    finally:
        clip.close()


def _hash_pliku(sciezka: Path) -> str:
    digest = hashlib.sha256()
    with sciezka.open("rb") as plik:
        for blok in iter(lambda: plik.read(1024 * 1024), b""):
            digest.update(blok)
    return digest.hexdigest()


def _wczytaj_stan(sciezka: Path) -> Dict[str, Dict[str, str]]:
    if not sciezka.exists():
        return {}
    try:
        dane = json.loads(sciezka.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as blad:
        raise RuntimeError(f"Nie można odczytać rejestru wysłanych filmów {sciezka}: {blad}") from blad
    if not isinstance(dane, dict):
        raise ValueError(f"Nieprawidłowy rejestr wysłanych filmów: {sciezka}")
    return dane


def _zapisz_stan(sciezka: Path, stan: Dict[str, Dict[str, str]]) -> None:
    tymczasowy = sciezka.with_suffix(sciezka.suffix + ".tmp")
    tymczasowy.write_text(
        json.dumps(stan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tymczasowy.replace(sciezka)


def _przeslij_film(
    youtube: Any,
    sciezka: Path,
    tytul: str,
    opis: str,
    termin: datetime,
) -> str:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": tytul,
            "description": opis,
            "categoryId": YOUTUBE_CATEGORY_SPORTS,
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": termin.astimezone(STREFA_CZASOWA).isoformat(),
        },
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(
            str(sciezka), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
        ),
    )
    odpowiedz = None
    while odpowiedz is None:
        _, odpowiedz = request.next_chunk()
    video_id = odpowiedz.get("id")
    if not video_id:
        raise RuntimeError("YouTube API nie zwróciło identyfikatora przesłanego filmu.")
    return video_id


def przetworz(
    sciezki: List[Path],
    youtube: Any,
    kanal: Dict[str, Any],
    publikuj: bool,
    plik_opisu: Path = PLIK_OPISU,
    plik_stanu: Path = PLIK_STANU,
) -> None:
    zajete_daty, zaplanowane, istniejace_tytuly = pobierz_kolejke(youtube, kanal)
    stan = _wczytaj_stan(plik_stanu)
    for film in zaplanowane:
        assert film.termin is not None
        print(f"[YT] W kolejce: {film.termin:%Y-%m-%d %H:%M} — {film.tytul}")
    for sciezka in sciezki:
        if not sciezka.is_file():
            raise FileNotFoundError(f"Nie znaleziono filmu: {sciezka}")
        _skrot_jest_poprawny(sciezka)
        tytul = generuj_tytul(sciezka, plik_opisu)
        hash_pliku = _hash_pliku(sciezka)
        if hash_pliku in stan:
            print(f"[YT] Pominięto film już wysłany: {sciezka.name}")
            continue
        if tytul.casefold() in istniejace_tytuly:
            print(f"[YT] Pominięto film o istniejącym tytule: {tytul}")
            continue

        termin = najblizszy_wolny_termin(
            zajete_daty, datetime.now(STREFA_CZASOWA)
        )
        opis, _ = generuj_opis_i_hashtagi(plik_opisu)
        if publikuj:
            sciezka = przemianuj_plik(sciezka, tytul)
            video_id = _przeslij_film(youtube, sciezka, tytul, opis, termin)
            stan[hash_pliku] = {"videoId": video_id, "title": tytul}
            _zapisz_stan(plik_stanu, stan)
            print(f"[YT] Wysłano {sciezka.name}: https://youtu.be/{video_id}")
        else:
            print(f"[PODGLĄD] {tytul} — {termin:%Y-%m-%d %H:%M} Europe/Warsaw")
        zajete_daty.add(termin.date())
        istniejace_tytuly.add(tytul.casefold())


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Sprawdza kolejkę YouTube i planuje lub przesyła gotowe Shorts."
    )
    parser.add_argument(
        "wejscie",
        nargs="?",
        type=Path,
        default=KATALOG_PROJEKTU / "Gotowe",
        help="Plik MP4 albo folder z gotowymi filmami (domyślnie Gotowe).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Wykonuje rzeczywisty upload; bez tej flagi tylko pokazuje podgląd.",
    )
    parser.add_argument("--opis", type=Path, default=PLIK_OPISU, help="Plik z opisem zawodów.")
    parser.add_argument(
        "--client-secrets",
        type=Path,
        default=Path(os.environ.get("YOUTUBE_CLIENT_SECRETS", PLIK_CLIENT_SECRETS)),
        help="Plik OAuth z Google Cloud.",
    )
    args = parser.parse_args(argv)

    if args.wejscie.is_dir():
        filmy = sorted(
            (plik for plik in args.wejscie.iterdir() if plik.suffix.lower() == ".mp4"),
            key=lambda plik: plik.name.casefold(),
        )
    else:
        filmy = [args.wejscie]
    if not filmy:
        parser.error(f"Nie znaleziono plików MP4 w {args.wejscie}")

    youtube = _autoryzuj(args.client_secrets, PLIK_TOKENU)
    channel_id = os.environ.get("YOUTUBE_CHANNEL_ID")
    kanal = _wybierz_kanal(youtube, channel_id)
    print(
        f"[YT] Kanał: {kanal.get('snippet', {}).get('title', kanal.get('id'))}"
    )
    przetworz(filmy, youtube, kanal, args.publish, args.opis)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as blad:
        print(f"[YT] BŁĄD: {blad}", file=sys.stderr)
        raise SystemExit(1) from blad
