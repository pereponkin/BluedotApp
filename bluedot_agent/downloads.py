from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DOWNLOAD_STATUS_SCRIPT = """
({kind, text, can_open}) => window.dispatchEvent(new CustomEvent(
  "bluedot-agent-download-status",
  { detail: { kind, text, can_open } }
))
"""
WINDOWS_DOWNLOADS_FOLDER_ID = "{374DE290-123F-4565-9164-39C4925E467B}"
WINDOWS_USER_SHELL_FOLDERS = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
)


def _windows_downloads_folder() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            WINDOWS_USER_SHELL_FOLDERS,
        ) as key:
            value, _ = winreg.QueryValueEx(key, WINDOWS_DOWNLOADS_FOLDER_ID)
        return str(value) if value else None
    except (OSError, ImportError):
        return None


def default_download_directory(
    *,
    platform: str = sys.platform,
    windows_folder: Callable[[], str | None] = _windows_downloads_folder,
) -> Path:
    override = os.environ.get("BLUEDOT_DOWNLOAD_DIR")
    if override:
        return Path(os.path.expandvars(override))

    if platform == "win32":
        value = windows_folder()
        if value:
            return Path(os.path.expandvars(value))

    return Path.home() / "Downloads"


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class DownloadManager:
    def __init__(self, directory: Path, *, log_path: Path | None = None) -> None:
        self.directory = directory
        self.log_path = log_path
        self.errors: list[str] = []
        self._tasks: set[asyncio.Task[None]] = set()
        self._reserved: set[Path] = set()
        self._reservation_lock = asyncio.Lock()
        self.last_saved_path: Path | None = None

    def set_directory(self, directory: Path) -> None:
        self.directory = Path(directory)

    def attach(self, context: Any) -> None:
        def attach_page(page: Any) -> None:
            page.on(
                "download",
                lambda download, source_page=page: self.queue(
                    download,
                    page=source_page,
                ),
            )

        for page in context.pages:
            attach_page(page)
        context.on("page", attach_page)

    def queue(self, download: Any, *, page: Any | None = None) -> None:
        filename = Path(download.suggested_filename).name or "bluedot-download"
        self._record("queued", filename=filename)
        task = asyncio.create_task(self._save(download, page=page))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self, timeout: float = 30.0) -> None:
        async def wait_for_all() -> None:
            while self._tasks:
                await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

        try:
            await asyncio.wait_for(wait_for_all(), timeout=timeout)
        except TimeoutError:
            pending = len(self._tasks)
            for task in tuple(self._tasks):
                task.cancel()
            self.errors.append(f"Timed out waiting for {pending} download(s)")

    async def _save(self, download: Any, *, page: Any | None = None) -> None:
        target: Path | None = None
        filename = Path(download.suggested_filename).name or "bluedot-download"
        directory = self.directory
        try:
            directory.mkdir(parents=True, exist_ok=True)
            await self._notify(
                page,
                "loading",
                f"Скачивание началось: {filename} → {directory}",
            )
            async with self._reservation_lock:
                target = available_download_path(
                    directory, download.suggested_filename, self._reserved
                )
                self._reserved.add(target)
            await download.save_as(str(target))
            self.last_saved_path = target
            self._record("saved", filename=filename, target=target)
            await self._notify(
                page,
                "success",
                f"Скачано: {target}",
                can_open=True,
            )
            if sys.stdout is not None:
                print(f"Скачано: {target}")
        except Exception as error:
            message = str(error).splitlines()[0] if str(error) else type(error).__name__
            self.errors.append(message)
            self._record(
                "failed",
                filename=filename,
                target=target,
                message=message,
            )
            await self._notify(
                page,
                "error",
                f"Не удалось скачать {filename}: {message}",
            )
            if sys.stdout is not None:
                print(f"Не удалось скачать файл: {message}")
        finally:
            if target is not None:
                async with self._reservation_lock:
                    self._reserved.discard(target)

    def open_last_download(self) -> bool:
        if self.last_saved_path is None or not self.last_saved_path.exists():
            return False
        open_path(self.last_saved_path)
        return True

    async def _notify(
        self,
        page: Any | None,
        kind: str,
        text: str,
        *,
        can_open: bool = False,
    ) -> None:
        if page is None:
            return
        try:
            await page.evaluate(
                DOWNLOAD_STATUS_SCRIPT,
                {"kind": kind, "text": text, **({"can_open": True} if can_open else {})},
            )
        except Exception:
            # A closed or navigating page must not turn a completed download into an error.
            return

    def _record(
        self,
        stage: str,
        *,
        filename: str,
        target: Path | None = None,
        message: str | None = None,
    ) -> None:
        if self.log_path is None:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "filename": filename,
            "target": str(target) if target is not None else None,
            "message": message,
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            return


def available_download_path(
    directory: Path,
    suggested_filename: str,
    reserved: set[Path] | None = None,
) -> Path:
    reserved = reserved or set()
    filename = Path(suggested_filename).name or "bluedot-download"
    candidate = directory / filename
    if not candidate.exists() and candidate not in reserved:
        return candidate

    suffix = Path(filename).suffix
    stem = Path(filename).stem
    index = 1
    while True:
        candidate = directory / f"{stem} ({index}){suffix}"
        if not candidate.exists() and candidate not in reserved:
            return candidate
        index += 1
