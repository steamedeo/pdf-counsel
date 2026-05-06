import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from filelock import FileLock

HISTORY_DIR = Path(__file__).parent.parent / "history"
HISTORY_FILE = HISTORY_DIR / "chat.json"
_HISTORY_LOCK = FileLock(str(HISTORY_FILE) + ".lock")
RETENTION_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cutoff() -> datetime:
    return _now() - timedelta(days=RETENTION_DAYS)


def _normalise_message(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None

    role = raw.get("role")
    content = raw.get("content")
    created_at = raw.get("created_at")
    if role not in {"user", "assistant"} or not isinstance(content, str) or not created_at:
        return None

    timestamp = _parse_iso(created_at)
    if timestamp is None or timestamp < _cutoff():
        return None

    citations = raw.get("citations") or []
    if not isinstance(citations, list):
        citations = []

    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "role": role,
        "content": content,
        "citations": citations,
        "created_at": timestamp.isoformat(),
    }


def _read_messages() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []

    try:
        payload = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    raw_messages = payload.get("messages", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_messages, list):
        return []

    messages = []
    for item in raw_messages:
        message = _normalise_message(item)
        if message:
            messages.append(message)

    messages.sort(key=lambda message: message["created_at"])
    return messages


def _write_messages(messages: list[dict]) -> None:
    HISTORY_DIR.mkdir(exist_ok=True)
    with _HISTORY_LOCK:
        HISTORY_FILE.write_text(
            json.dumps({"messages": messages}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def list_messages() -> list[dict]:
    messages = _read_messages()
    _write_messages(messages)
    return messages


def save_message(role: str, content: str, citations: list[dict] | None = None) -> dict:
    messages = _read_messages()
    message = {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "citations": citations or [],
        "created_at": _now().isoformat(),
    }
    messages.append(message)
    messages.sort(key=lambda item: item["created_at"])
    _write_messages(messages)
    return message


def clear_messages() -> dict:
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    return {"status": "deleted"}
