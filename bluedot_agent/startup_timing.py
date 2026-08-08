from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable
from uuid import uuid4

from .config import STATE_DIR


STARTUP_LOG_PATH = STATE_DIR / "startup.log"


class StartupTimer:
    def __init__(
        self,
        *,
        path: Path | None = None,
        started_at: float | None = None,
        elapsed_offset_ms: float = 0.0,
        clock: Callable[[], float] = perf_counter,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path or STARTUP_LOG_PATH
        self._clock = clock
        self._wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self._started_at = clock() if started_at is None else started_at
        self._elapsed_offset_ms = max(0.0, elapsed_offset_ms)
        self._run_id = uuid4().hex[:12]
        self._write("process_started", 0)

    def mark(self, stage: str, *, detail: str | None = None) -> int:
        elapsed_ms = round(
            self._elapsed_offset_ms
            + (self._clock() - self._started_at) * 1000
        )
        self._write(stage, elapsed_ms, detail=detail)
        return elapsed_ms

    def _write(
        self,
        stage: str,
        elapsed_ms: int,
        *,
        detail: str | None = None,
    ) -> None:
        entry = {
            "timestamp": self._wall_clock().isoformat(),
            "run_id": self._run_id,
            "elapsed_ms": elapsed_ms,
            "stage": stage,
        }
        if detail:
            entry["detail"] = detail
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            # Timing must never prevent the agent itself from starting.
            return
