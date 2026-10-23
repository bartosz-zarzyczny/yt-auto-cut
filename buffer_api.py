"""Klient GraphQL API Buffer (https://developers.buffer.com/)."""
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

API_URL = "https://api.buffer.com"
REQUEST_TIMEOUT_SECONDS = 30
MAX_POST_PAGES = 50

CREATE_POST_MUTATION = """mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post {
        id
        dueAt
      }
    }
    ... on MutationError {
      message
    }
  }
}"""


class BufferApiError(Exception):
    """Błąd komunikacji z Buffer; komunikat trafia do użytkownika."""


def _request(token: str, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "yt-auto-cut",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise BufferApiError(f"Buffer odrzucił zapytanie (HTTP {error.code}). Sprawdź klucz BUFFER_API.") from error
    except (urllib.error.URLError, OSError) as error:
        raise BufferApiError(f"Nie udało się połączyć z Buffer: {error}") from error
    except ValueError as error:
        raise BufferApiError("Buffer zwrócił nieprawidłową odpowiedź.") from error

    errors = payload.get("errors")
    if errors:
        messages = "; ".join(str(item.get("message", item)) for item in errors)
        raise BufferApiError(f"Buffer zwrócił błąd: {messages}")
    return payload.get("data") or {}


def get_organization_id(token: str) -> str:
    data = _request(token, "query { account { organizations { id } } }")
    organizations = (data.get("account") or {}).get("organizations") or []
    if not organizations:
        raise BufferApiError("Konto Buffer nie ma żadnej organizacji.")
    return organizations[0]["id"]


def get_channels(token: str, organization_id: str) -> List[Dict[str, str]]:
    query = (
        "query { channels(input: { organizationId: "
        f"{json.dumps(organization_id)}"
        " }) { id name service } }"
    )
    return _request(token, query).get("channels") or []


def get_due_dates(token: str, organization_id: str, channel_ids: List[str]) -> List[str]:
    """Zwraca terminy (ISO 8601) wszystkich postów i szkiców wskazanych kanałów."""
    due_dates: List[str] = []
    cursor: Optional[str] = None
    for _ in range(MAX_POST_PAGES):
        after = f", after: {json.dumps(cursor)}" if cursor else ""
        query = (
            f"query {{ posts(first: 100{after}, input: {{ organizationId: {json.dumps(organization_id)}, "
            f"filter: {{ channelIds: {json.dumps(channel_ids)} }} }}) "
            "{ edges { node { dueAt } } pageInfo { hasNextPage endCursor } } }"
        )
        page = _request(token, query).get("posts") or {}
        for edge in page.get("edges") or []:
            due_at = (edge.get("node") or {}).get("dueAt")
            if due_at:
                due_dates.append(due_at)
        page_info = page.get("pageInfo") or {}
        if not page_info.get("hasNextPage") or not page_info.get("endCursor"):
            break
        cursor = page_info["endCursor"]
    return due_dates


def create_draft(
    token: str,
    channel_id: str,
    text: str,
    due_at: datetime,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Tworzy szkic posta (bez publikacji) z terminem `due_at`; zwraca identyfikator posta."""
    post_input: Dict[str, Any] = {
        "text": text,
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "customScheduled",
        "dueAt": due_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "saveToDraft": True,
    }
    if metadata:
        post_input["metadata"] = metadata
    variables = {"input": post_input}
    result = _request(token, CREATE_POST_MUTATION, variables).get("createPost") or {}
    post = result.get("post")
    if not post:
        raise BufferApiError(f"Buffer nie utworzył szkicu: {result.get('message') or 'brak szczegółów'}")
    return post["id"]
