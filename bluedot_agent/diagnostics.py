from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .config import LOG_DIR


SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "x-goog-api-key",
}


@dataclass(frozen=True)
class NetworkEvent:
    direction: str
    method: str
    url: str
    resource_type: str
    status: int | None = None
    post_data: str | None = None
    body_preview: str | None = None


class PendingTasks:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def create(self, awaitable: Any) -> None:
        task = asyncio.create_task(awaitable)
        self._tasks.add(task)
        task.add_done_callback(self._finish)

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    def _finish(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if not task.cancelled():
            task.exception()


def redact(value: Any, key: str = "") -> Any:
    if key.casefold() in SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str) and (
        key.casefold() == "url" or value.startswith(("http://", "https://"))
    ):
        return strip_url_query(value)
    if isinstance(value, str) and key.casefold() in {"post_data", "body_preview"}:
        return redact_payload_text(value)
    return value


def strip_url_query(url: str) -> str:
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except ValueError:
        return "[INVALID URL]"


def redact_payload_text(value: str) -> str:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        pattern = re.compile(
            r'(?i)(authorization|cookie|password|access_token|refresh_token|api_key|apikey|x-goog-api-key|token)'
            r'(["\s:=]+)([^&\s,}\"]+)'
        )
        return pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)
    return json.dumps(redact(parsed), ensure_ascii=False, separators=(",", ":"))


def write_json_log(
    prefix: str,
    data: Any,
    *,
    log_dir: Path = LOG_DIR,
    keep: int = 20,
) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = log_dir / f"{prefix}_{stamp}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(redact(data), handle, ensure_ascii=False, indent=2)
    _trim_logs(log_dir, prefix, keep)
    return path


def diagnostic_path(prefix: str, extension: str, *, log_dir: Path = LOG_DIR) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return log_dir / f"{prefix}_{stamp}.{extension.lstrip('.')}"


def _trim_logs(log_dir: Path, prefix: str, keep: int) -> None:
    paths = sorted(log_dir.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths[max(0, keep):]:
        path.unlink(missing_ok=True)
