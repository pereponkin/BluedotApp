from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Mapping

from .browser import BROWSER_KINDS, BrowserKind


class InstanceAlreadyRunning(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle = None

    def __enter__(self) -> InstanceLock:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("a+b")
        self._handle.seek(0, os.SEEK_END)
        if self._handle.tell() == 0:
            self._handle.write(b"\0")
            self._handle.flush()
        self._handle.seek(0)
        try:
            self._lock()
        except OSError as error:
            self._handle.close()
            self._handle = None
            raise InstanceAlreadyRunning(
                "Blue Dot Agent уже запущен. Закройте его браузер и повторите запуск."
            ) from error
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._handle is None:
            return
        self._unlock()
        self._handle.close()
        self._handle = None

    def _lock(self) -> None:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(self) -> None:
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)


def chrome_is_available(
    *,
    platform: str = sys.platform,
    exists: Callable[[Path], bool] = Path.exists,
    which: Callable[[str], str | None] = shutil.which,
) -> bool:
    """Return whether Playwright's stable Google Chrome channel is installed."""

    if platform == "win32":
        roots = (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        )
        if any(
            root
            and exists(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")
            for root in roots
        ):
            return True
    elif platform == "darwin":
        if exists(Path("/Applications/Google Chrome.app")) or exists(
            Path.home() / "Applications" / "Google Chrome.app"
        ):
            return True
    return which("google-chrome") is not None or which("chrome") is not None


def choose_browser(
    *,
    chrome_available: Callable[[], bool] = chrome_is_available,
) -> BrowserKind:
    """Show the first-launch browser chooser outside the browser page DOM."""

    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError as error:
        raise OSError("Не удалось открыть окно выбора браузера.") from error

    selected: list[BrowserKind] = []
    root = tk.Tk()
    root.title("Blue Dot Agent — первый запуск")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = ttk.Frame(root, padding=20)
    frame.grid()
    ttk.Label(
        frame,
        text="В каком браузере открыть Blue Dot Agent?",
        font=("TkDefaultFont", 11, "bold"),
    ).grid(row=0, column=0, columnspan=2, pady=(0, 8))
    ttk.Label(
        frame,
        text="Firefox будет скачан при первом выборе. Позже браузер можно изменить в настройках.",
    ).grid(row=1, column=0, columnspan=2, pady=(0, 16))

    def finish(browser: BrowserKind) -> None:
        if browser == "chrome" and not chrome_available():
            messagebox.showerror(
                "Google Chrome не найден",
                "Установите Google Chrome с google.com/chrome и повторите выбор.",
                parent=root,
            )
            return
        selected.append(browser)
        root.destroy()

    ttk.Button(frame, text="Firefox", command=lambda: finish("firefox")).grid(
        row=2, column=0, padx=(0, 6), sticky="ew"
    )
    ttk.Button(frame, text="Google Chrome", command=lambda: finish("chrome")).grid(
        row=2, column=1, padx=(6, 0), sticky="ew"
    )
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.after_idle(lambda: (root.lift(), root.focus_force()))
    root.mainloop()
    if not selected:
        raise RuntimeError("Выбор браузера отменён.")
    return selected[0]


def resolve_browser(
    *,
    cli_browser: str | None,
    environ: Mapping[str, str],
    settings,
    chooser: Callable[[], BrowserKind],
) -> BrowserKind:
    requested = cli_browser or environ.get("BLUEDOT_BROWSER", "").strip() or None
    if requested is not None:
        normalized = requested.casefold()
        if normalized not in BROWSER_KINDS:
            raise ValueError("Неизвестный браузер. Используйте firefox или chrome.")
        return normalized
    if settings.has_saved_browser():
        return settings.browser()
    selected = chooser()
    settings.save_browser(selected)
    return selected
