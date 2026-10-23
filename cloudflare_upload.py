"""Wysyłanie filmów MP4 do Cloudflare R2 (S3 API) i zapisywanie ich linków do listy Buffer."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Tuple
from urllib.parse import quote, urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from boto3.s3.transfer import TransferConfig

VIDEO_EXTENSION = ".mp4"
VIDEO_CONTENT_TYPE = "video/mp4"
REGION = "auto"
MISSING_OBJECT_CODES = ("404", "NoSuchKey", "NotFound")
TRANSFER_CONFIG = TransferConfig(multipart_chunksize=64 * 1024 * 1024, max_concurrency=8)
CLIENT_CONFIG = Config(
    retries={"max_attempts": 5, "mode": "standard"},
    # R2 nie obsługuje domyślnych sum kontrolnych wprowadzanych przez nowsze boto3.
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
)


class CloudflareUploadError(Exception):
    """Błąd wysyłki do Cloudflare; komunikat trafia do użytkownika."""


@dataclass(frozen=True)
class CloudflareConfig:
    endpoint_url: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    public_url: str


def parse_endpoint(value: str) -> Tuple[str, str]:
    """Rozdziela adres z settings.json (np. https://<konto>.r2.cloudflarestorage.com/buffer-api) na endpoint i bucket."""
    parts = urlsplit(value.strip())
    bucket = parts.path.strip("/").split("/")[0]
    if parts.scheme not in ("http", "https") or not parts.netloc or not bucket:
        raise CloudflareUploadError(
            "Nieprawidłowy adres CLOUDFLARE_API w settings.json. Oczekiwano https://<konto>.r2.cloudflarestorage.com/<bucket>."
        )
    return f"{parts.scheme}://{parts.netloc}", bucket


def build_config(values: dict) -> CloudflareConfig:
    """Tworzy konfigurację z wartości wczytanych z settings.json; brak wymaganego pola kończy się błędem."""
    missing = [
        key
        for key in ("CLOUDFLARE_API", "CLOUDFLARE_ACCESS_KEY_ID", "CLOUDFLARE_SECRET_ACCESS_KEY", "CLOUDFLARE_PUBLIC_URL")
        if not values.get(key)
    ]
    if missing:
        raise CloudflareUploadError("Uzupełnij w settings.json: " + ", ".join(missing) + ".")
    endpoint_url, bucket = parse_endpoint(values["CLOUDFLARE_API"])
    public_host = urlsplit(values["CLOUDFLARE_PUBLIC_URL"]).netloc
    if public_host.endswith(".r2.cloudflarestorage.com"):
        raise CloudflareUploadError(
            "CLOUDFLARE_PUBLIC_URL wskazuje na endpoint S3, a nie na publiczny adres. "
            "Włącz Public access dla bucketa w Cloudflare R2 i wpisz adres https://pub-….r2.dev lub własnej domeny."
        )
    return CloudflareConfig(
        endpoint_url=endpoint_url,
        bucket=bucket,
        access_key_id=values["CLOUDFLARE_ACCESS_KEY_ID"],
        secret_access_key=values["CLOUDFLARE_SECRET_ACCESS_KEY"],
        public_url=values["CLOUDFLARE_PUBLIC_URL"].rstrip("/"),
    )


def create_client(config: CloudflareConfig):
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=REGION,
        config=CLIENT_CONFIG,
    )


def public_link(public_url: str, file_name: str) -> str:
    return f"{public_url.rstrip('/')}/{quote(file_name)}"


def list_videos(folder: Path) -> List[Path]:
    return sorted(
        path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == VIDEO_EXTENSION
    )


def object_exists(client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in MISSING_OBJECT_CODES:
            return False
        raise


def upload_video(client, bucket: str, path: Path) -> bool:
    """Wysyła plik pod nazwą jego pliku; zwraca False, gdy obiekt o tej nazwie już istnieje."""
    if object_exists(client, bucket, path.name):
        return False
    client.upload_file(
        str(path),
        bucket,
        path.name,
        ExtraArgs={"ContentType": VIDEO_CONTENT_TYPE},
        Config=TRANSFER_CONFIG,
    )
    return True


def append_link_to_list(list_path: Path, link: str) -> bool:
    """Dopisuje link na końcu listy, jeśli go tam jeszcze nie ma; zwraca True po dopisaniu."""
    existing = list_path.read_text(encoding="utf-8") if list_path.exists() else ""
    if link in existing.split():
        return False
    separator = "" if not existing or existing.endswith("\n") else "\n"
    with list_path.open("a", encoding="utf-8") as file:
        file.write(f"{separator}{link}\n")
    return True


def upload_folder(
    config: CloudflareConfig,
    folder: Path,
    list_path: Path,
    log: Callable[[str], None],
    on_link: Callable[[str], None],
    is_cancelled: Callable[[], bool] = lambda: False,
) -> Tuple[int, int, int]:
    """Wysyła wszystkie MP4 z folderu; po każdym pliku dopisuje link do listy. Zwraca (wysłane, istniejące, błędy)."""
    videos = list_videos(folder)
    if not videos:
        raise CloudflareUploadError(f"W folderze nie ma plików MP4: {folder}")
    client = create_client(config)
    sent = 0
    existing = 0
    failed = 0
    for path in videos:
        if is_cancelled():
            log("[Cloudflare] Przerwano na żądanie użytkownika.")
            break
        try:
            log(f"[Cloudflare] Wysyłanie: {path.name}")
            if upload_video(client, config.bucket, path):
                sent += 1
                log(f"[Cloudflare] Wysłano: {path.name}")
            else:
                existing += 1
                log(f"[Cloudflare] Już istnieje w bucketcie, pomijam wysyłanie: {path.name}")
        except (BotoCoreError, ClientError, OSError) as error:
            failed += 1
            log(f"[Cloudflare] BŁĄD przy {path.name}: {error}")
            continue
        link = public_link(config.public_url, path.name)
        if append_link_to_list(list_path, link):
            log(f"[Cloudflare] Dopisano link do listy Buffer: {link}")
        on_link(link)
    log(f"[Cloudflare] Wysłano: {sent}, już istniały: {existing}, błędy: {failed}.")
    return sent, existing, failed
