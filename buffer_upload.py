"""Tworzenie szkiców postów w Buffer na podstawie listy publicznych adresów plików wideo (np. Cloudflare R2)."""
import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from buffer_api import BufferApiError, create_draft, get_channels, get_due_dates, get_organization_id
from youtube_upload import TIME_ZONE, nearest_free_slot

PROJECT_DIR = Path(__file__).resolve().parent
STATE_FILE = PROJECT_DIR / "buffer_upload_state.json"
STATE_SAVE_ATTEMPTS = 10
STATE_SAVE_DELAY_SECONDS = 0.5

PLATFORM_FACEBOOK = "facebook"
PLATFORM_INSTAGRAM = "instagram"
PLATFORM_X = "x"

# Klucz: identyfikator platformy w aplikacji, wartość: nazwa usługi w Buffer.
BUFFER_SERVICES = {
    PLATFORM_FACEBOOK: "facebook",
    PLATFORM_INSTAGRAM: "instagram",
    PLATFORM_X: "twitter",
}
PLATFORM_LABELS = {
    PLATFORM_FACEBOOK: "Facebook",
    PLATFORM_INSTAGRAM: "Instagram",
    PLATFORM_X: "X/Twitter",
}

# Buffer wymaga typu posta dla Facebooka i Instagrama (post, story lub reel).
POST_TYPES = ("reel", "post", "story")
DEFAULT_POST_TYPE = "reel"
TYPED_SERVICES = {PLATFORM_FACEBOOK: "facebook", PLATFORM_INSTAGRAM: "instagram"}

INSTAGRAM_MAX_HASHTAGS = 5
X_MAX_CHARS = 280
X_URL_LENGTH = 23

URL_PATTERN = re.compile(r"https?://\S+")
HASHTAG_PATTERN = re.compile(r"#\w+")


def parse_video_links(text: str) -> List[str]:
    """Zwraca adresy plików wideo z tekstu w kolejności pojawiania się, bez duplikatów."""
    links: List[str] = []
    for match in URL_PATTERN.findall(text):
        link = match.rstrip(".,;)")
        if link not in links:
            links.append(link)
    return links


def count_hashtags(text: str) -> int:
    return len(HASHTAG_PATTERN.findall(text))


def x_text_length(text: str) -> int:
    """Długość tekstu wg zasad X: każdy adres URL liczy się jako 23 znaki."""
    without_urls = URL_PATTERN.sub("", text)
    return len(without_urls) + len(URL_PATTERN.findall(text)) * X_URL_LENGTH


def find_text_problems(platforms: Sequence[str], descriptions: Dict[str, str]) -> List[str]:
    """Zwraca komunikaty (po polsku) o przekroczonych limitach dla wybranych platform."""
    problems: List[str] = []
    if PLATFORM_INSTAGRAM in platforms:
        hashtags = count_hashtags(descriptions.get(PLATFORM_INSTAGRAM, ""))
        if hashtags > INSTAGRAM_MAX_HASHTAGS:
            problems.append(
                f"Opis na Instagram ma {hashtags} hashtagów, a limit to {INSTAGRAM_MAX_HASHTAGS}."
            )
    if PLATFORM_X in platforms:
        length = x_text_length(descriptions.get(PLATFORM_X, "").strip())
        if length > X_MAX_CHARS:
            problems.append(f"Opis na X/Twitter ma {length} znaków, a limit to {X_MAX_CHARS}.")
    return problems


def _load_state(path: Path) -> Dict[str, Dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(path: Path, state: Dict[str, Dict[str, str]]) -> None:
    content = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    for attempt in range(STATE_SAVE_ATTEMPTS):
        try:
            temp_path.replace(path)
            return
        except PermissionError:
            time.sleep(STATE_SAVE_DELAY_SECONDS)
    path.write_text(content, encoding="utf-8")
    temp_path.unlink(missing_ok=True)


def _local_date(due_at: str) -> Optional[date]:
    try:
        parsed = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(TIME_ZONE).date()


def _resolve_channels(
    token: str, organization_id: str, platforms: Sequence[str], log: Callable[[str], None]
) -> Dict[str, str]:
    channels = get_channels(token, organization_id)
    channel_ids: Dict[str, str] = {}
    for platform in platforms:
        service = BUFFER_SERVICES[platform]
        matching = [channel for channel in channels if channel.get("service") == service]
        if not matching:
            raise BufferApiError(
                f"W Buffer nie znaleziono kanału {PLATFORM_LABELS[platform]} (usługa: {service})."
            )
        if len(matching) > 1:
            log(f"[Buffer] Więcej kanałów {service}, używam: {matching[0].get('name')}")
        channel_ids[platform] = matching[0]["id"]
    return channel_ids


def build_metadata(platform: str, post_types: Dict[str, str]) -> Optional[dict]:
    service = TYPED_SERVICES.get(platform)
    if service is None:
        return None
    post_type = post_types.get(platform, DEFAULT_POST_TYPE)
    if post_type not in POST_TYPES:
        raise BufferApiError(f"Nieznany typ posta: {post_type}")
    if service == "instagram":
        return {service: {"type": post_type, "shouldShareToFeed": True}}
    return {service: {"type": post_type}}


def send_drafts(
    token: str,
    links: Sequence[str],
    platforms: Sequence[str],
    descriptions: Dict[str, str],
    hours: Optional[Dict[int, object]],
    log: Callable[[str], None],
    state_file: Path = STATE_FILE,
    is_cancelled: Callable[[], bool] = lambda: False,
    now: Optional[datetime] = None,
    post_types: Optional[Dict[str, str]] = None,
) -> Tuple[int, int]:
    """Tworzy szkice dla każdego linku w jednym wolnym terminie; zwraca (utworzone, pominięte)."""
    if not links:
        raise BufferApiError("Lista filmów jest pusta.")
    if not platforms:
        raise BufferApiError("Nie wybrano żadnej platformy.")
    post_types = post_types or {}

    organization_id = get_organization_id(token)
    channel_ids = _resolve_channels(token, organization_id, platforms, log)
    taken: Set[date] = set()
    for due_at in get_due_dates(token, organization_id, list(channel_ids.values())):
        local_day = _local_date(due_at)
        if local_day:
            taken.add(local_day)

    state = _load_state(state_file)
    created = 0
    skipped = 0
    for link in links:
        if is_cancelled():
            log("[Buffer] Przerwano na żądanie użytkownika.")
            break
        pending = [p for p in platforms if f"{p}|{link}" not in state]
        if not pending:
            log(f"[Buffer] Pominięto już wysłany film: {link}")
            skipped += 1
            continue

        existing_due = [state[f"{p}|{link}"]["dueAt"] for p in platforms if f"{p}|{link}" in state]
        if existing_due:
            slot = datetime.fromisoformat(existing_due[0])
        else:
            slot = nearest_free_slot(taken, now, hours)
            taken.add(slot.date())
        text_by_platform = {p: descriptions.get(p, "").strip() for p in pending}
        log(f"[Buffer] {link} -> termin {slot:%Y-%m-%d %H:%M}")
        for platform in pending:
            metadata = build_metadata(platform, post_types)
            post_id = create_draft(
                token, channel_ids[platform], text_by_platform[platform], slot, link, metadata
            )
            state[f"{platform}|{link}"] = {
                "postId": post_id,
                "dueAt": slot.isoformat(),
            }
            _save_state(state_file, state)
            created += 1
            log(f"[Buffer] Szkic utworzony: {PLATFORM_LABELS[platform]} ({post_id})")
    log(f"[Buffer] Utworzono szkiców: {created}, pominięto: {skipped}.")
    return created, skipped
