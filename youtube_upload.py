import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from moviepy.editor import VideoFileClip

from generate_names import (
    DESCRIPTION_FILE,
    PROJECT_DIR,
    generate_description_and_hashtags,
    generate_title,
    rename_file,
)

TIME_ZONE = ZoneInfo("Europe/Warsaw")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
CLIENT_SECRETS_FILE = PROJECT_DIR / "youtube_client_secret.json"
TOKEN_FILE = PROJECT_DIR / "youtube_token.json"
STATE_FILE = PROJECT_DIR / "youtube_upload_state.json"
YOUTUBE_CATEGORY_SPORTS = "17"
MAX_SHORTS_SECONDS = 180


@dataclass(frozen=True)
class QueuedVideo:
    video_id: str
    title: str
    scheduled_at: Optional[datetime]


def nearest_free_slot(
    taken_dates: Set[date],
    now: Optional[datetime] = None,
    hours: Optional[Dict[int, time]] = None,
) -> datetime:
    """Zwraca najbliższy wolny termin; `hours` mapuje dzień tygodnia (0=pon) na godzinę."""
    now = now or datetime.now(TIME_ZONE)
    if now.tzinfo is None:
        raise ValueError("Bieżący czas musi zawierać informację o strefie czasowej.")
    now = now.astimezone(TIME_ZONE)
    day = now.date()
    while True:
        if hours:
            hour = hours.get(day.weekday())
        else:
            hour = time(10, 0) if day.weekday() >= 5 else time(7, 30)
        if hour is not None:
            slot = datetime.combine(day, hour, tzinfo=TIME_ZONE)
            if day not in taken_dates and slot > now:
                return slot
        day += timedelta(days=1)


def _authorize(client_secrets: Path, token_file: Path) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as error:
        raise RuntimeError(
            "Brak bibliotek Google API. Zainstaluj zależności: "
            "python -m pip install -r requirements.txt"
        ) from error

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


def _choose_channel(
    youtube: Any, channel_id: Optional[str]
) -> Dict[str, Any]:
    response = youtube.channels().list(part="id,snippet,contentDetails", mine=True).execute()
    channels = response.get("items", [])
    if channel_id:
        channels = [channel for channel in channels if channel.get("id") == channel_id]
        if not channels:
            raise ValueError(
                f"Konto OAuth nie zwróciło wskazanego kanału YouTube: {channel_id}"
            )
    if len(channels) != 1:
        names = ", ".join(
            f"{channel.get('snippet', {}).get('title', 'bez nazwy')} ({channel.get('id')})"
            for channel in channels
        ) or "brak kanałów"
        raise ValueError(
            f"Nie można jednoznacznie wybrać kanału ({names}). "
            "Ustaw zmienną YOUTUBE_CHANNEL_ID na ID właściwego kanału."
        )
    return channels[0]


def fetch_queue(
    youtube: Any, channel: Dict[str, Any]
) -> Tuple[Set[date], List[QueuedVideo], Set[str]]:
    uploads_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    video_ids: List[str] = []
    page_token = None
    while True:
        response = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()
        video_ids.extend(
            element["contentDetails"]["videoId"]
            for element in response.get("items", [])
            if element.get("contentDetails", {}).get("videoId")
        )
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    taken_dates: Set[date] = set()
    scheduled: List[QueuedVideo] = []
    existing_titles: Set[str] = set()
    for start in range(0, len(video_ids), 50):
        response = youtube.videos().list(
            part="snippet,status",
            id=",".join(video_ids[start:start + 50]),
            maxResults=50,
        ).execute()
        for video in response.get("items", []):
            title = video.get("snippet", {}).get("title", "")
            if title:
                existing_titles.add(title.casefold())
            status = video.get("status", {})
            publish_at = status.get("publishAt")
            scheduled_at = None
            if publish_at:
                scheduled_at = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
                if scheduled_at.tzinfo is None:
                    raise ValueError(f"Nieprawidłowy termin publikacji z API: {publish_at}")
                scheduled_at = scheduled_at.astimezone(TIME_ZONE)
                taken_dates.add(scheduled_at.date())
                scheduled.append(QueuedVideo(video["id"], title, scheduled_at))
            elif status.get("privacyStatus") in {"public", "unlisted"}:
                published_at = video.get("snippet", {}).get("publishedAt")
                if published_at:
                    published_on = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    ).astimezone(TIME_ZONE)
                    taken_dates.add(published_on.date())
    scheduled.sort(key=lambda video: video.scheduled_at or datetime.max.replace(tzinfo=TIME_ZONE))
    return taken_dates, scheduled, existing_titles


def _validate_short(path: Path) -> None:
    clip = VideoFileClip(str(path))
    try:
        if clip.duration is None or clip.duration > MAX_SHORTS_SECONDS:
            raise ValueError(
                f"{path.name}: Shorts muszą mieć maksymalnie "
                f"{MAX_SHORTS_SECONDS} sekund."
            )
        if clip.h < clip.w:
            raise ValueError(
                f"{path.name}: Short musi mieć format pionowy lub kwadratowy "
                f"(plik ma {clip.w}x{clip.h})."
            )
    finally:
        clip.close()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_state(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Nie można odczytać rejestru wysłanych filmów {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Nieprawidłowy rejestr wysłanych filmów: {path}")
    return data


def _save_state(path: Path, state: Dict[str, Dict[str, str]]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp_path.replace(path)


class UploadCancelled(Exception):
    """Użytkownik przerwał wysyłanie filmów."""


def _check_cancelled(cancel_event: Optional[Any]) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise UploadCancelled("Wysyłanie przerwano przez użytkownika.")


def _upload_video(
    youtube: Any,
    path: Path,
    title: str,
    description: str,
    scheduled_at: Optional[datetime],
    cancel_event: Optional[Any] = None,
) -> str:
    from googleapiclient.http import MediaFileUpload

    status: Dict[str, Any] = {"privacyStatus": "public"}
    if scheduled_at is not None:
        status = {
            "privacyStatus": "private",
            "publishAt": scheduled_at.astimezone(TIME_ZONE).isoformat(),
        }
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": YOUTUBE_CATEGORY_SPORTS,
        },
        "status": status,
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(
            str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
        ),
    )
    response = None
    while response is None:
        _check_cancelled(cancel_event)
        _, response = request.next_chunk()
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube API nie zwróciło identyfikatora przesłanego filmu.")
    return video_id


def process_videos(
    paths: List[Path],
    youtube: Any,
    channel: Dict[str, Any],
    publish: bool,
    description_file: Path = DESCRIPTION_FILE,
    state_file: Path = STATE_FILE,
    log: Callable[[str], None] = print,
    cancel_event: Optional[Any] = None,
    hours: Optional[Dict[int, time]] = None,
    immediate: bool = False,
) -> None:
    taken_dates, scheduled, existing_titles = fetch_queue(youtube, channel)
    state = _load_state(state_file)
    for video in scheduled:
        assert video.scheduled_at is not None
        log(f"[YT] W kolejce: {video.scheduled_at:%Y-%m-%d %H:%M} — {video.title}")
    for path in paths:
        _check_cancelled(cancel_event)
        if not path.is_file():
            raise FileNotFoundError(f"Nie znaleziono filmu: {path}")
        _validate_short(path)
        title = generate_title(path, description_file)
        content_hash = _file_hash(path)
        if content_hash in state:
            log(f"[YT] Pominięto film już wysłany: {path.name}")
            continue
        if title.casefold() in existing_titles:
            log(f"[YT] Pominięto film o istniejącym tytule: {title}")
            continue

        scheduled_at = None
        if not immediate:
            scheduled_at = nearest_free_slot(
                taken_dates, datetime.now(TIME_ZONE), hours
            )
        description, _ = generate_description_and_hashtags(description_file)
        if publish:
            path = rename_file(path, title)
            log(f"[YT] Wysyłanie: {path.name}…")
            video_id = _upload_video(youtube, path, title, description, scheduled_at, cancel_event)
            state[content_hash] = {"videoId": video_id, "title": title}
            _save_state(state_file, state)
            log(f"[YT] Wysłano {path.name}: https://youtu.be/{video_id}")
        elif scheduled_at is None:
            log(f"[PODGLĄD] {title} — publikacja od razu")
        else:
            log(f"[PODGLĄD] {title} — {scheduled_at:%Y-%m-%d %H:%M} Europe/Warsaw")
        if scheduled_at is not None:
            taken_dates.add(scheduled_at.date())
        existing_titles.add(title.casefold())


def upload_videos(
    videos: List[Path],
    publish: bool,
    description_file: Path = DESCRIPTION_FILE,
    client_secrets: Path = CLIENT_SECRETS_FILE,
    log: Callable[[str], None] = print,
    cancel_event: Optional[Any] = None,
    hours: Optional[Dict[int, time]] = None,
    immediate: bool = False,
) -> None:
    youtube = _authorize(client_secrets, TOKEN_FILE)
    _check_cancelled(cancel_event)
    channel = _choose_channel(youtube, os.environ.get("YOUTUBE_CHANNEL_ID"))
    log(f"[YT] Kanał: {channel.get('snippet', {}).get('title', channel.get('id'))}")
    process_videos(
        videos, youtube, channel, publish, description_file,
        log=log, cancel_event=cancel_event, hours=hours, immediate=immediate,
    )


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Sprawdza kolejkę YouTube i planuje lub przesyła gotowe Shorts."
    )
    parser.add_argument(
        "wejscie",
        nargs="?",
        type=Path,
        default=PROJECT_DIR / "Gotowe",
        help="Plik MP4 albo folder z gotowymi filmami (domyślnie Gotowe).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Wykonuje rzeczywisty upload; bez tej flagi tylko pokazuje podgląd.",
    )
    parser.add_argument(
        "--opis", dest="description_file", type=Path, default=DESCRIPTION_FILE,
        help="Plik z opisem zawodów.",
    )
    parser.add_argument(
        "--client-secrets",
        type=Path,
        default=Path(os.environ.get("YOUTUBE_CLIENT_SECRETS", CLIENT_SECRETS_FILE)),
        help="Plik OAuth z Google Cloud.",
    )
    args = parser.parse_args(argv)

    if args.wejscie.is_dir():
        videos = sorted(
            (file for file in args.wejscie.iterdir() if file.suffix.lower() == ".mp4"),
            key=lambda file: file.name.casefold(),
        )
    else:
        videos = [args.wejscie]
    if not videos:
        parser.error(f"Nie znaleziono plików MP4 w {args.wejscie}")

    upload_videos(videos, args.publish, args.description_file, args.client_secrets)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as error:
        print(f"[YT] BŁĄD: {error}", file=sys.stderr)
        raise SystemExit(1) from error
