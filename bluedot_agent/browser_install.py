from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Any

from playwright._impl._driver import compute_driver_executable, get_driver_env

from .config import STATE_DIR


def configure_browser_cache(
    *,
    state_dir: Path = STATE_DIR,
    environ: MutableMapping[str, str] = os.environ,
) -> Path:
    cache = state_dir / "browsers"
    environ["PLAYWRIGHT_BROWSERS_PATH"] = str(cache)
    return cache


def firefox_is_installed() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            return Path(playwright.firefox.executable_path).is_file()
    except Exception:
        return False


def install_firefox(
    cache: Path,
    *,
    run: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    executable, cli = compute_driver_executable()
    environment = get_driver_env()
    environment["PLAYWRIGHT_BROWSERS_PATH"] = str(cache)
    result = run(
        [executable, cli, "install", "firefox"],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        suffix = f" Деталь: {detail[-1]}" if detail else ""
        raise RuntimeError(f"Не удалось скачать Firefox для Blue Dot Agent.{suffix}")


def ensure_firefox_installed(
    *,
    state_dir: Path = STATE_DIR,
    environ: MutableMapping[str, str] = os.environ,
    frozen: bool | None = None,
) -> None:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not is_frozen:
        _, cli = compute_driver_executable()
        development_cache = Path(cli).parent / ".local-browsers"
        if development_cache.is_dir():
            environ["PLAYWRIGHT_BROWSERS_PATH"] = str(development_cache)
            if firefox_is_installed():
                return

    cache = configure_browser_cache(state_dir=state_dir, environ=environ)
    if firefox_is_installed():
        return
    _download_firefox_dialog(cache)
    if not firefox_is_installed():
        raise RuntimeError("Firefox скачан, но его исполняемый файл не найден.")


def _download_firefox_dialog(cache: Path) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError as error:
        raise OSError("Не удалось открыть окно установки Firefox.") from error

    root = tk.Tk()
    root.withdraw()
    accepted = messagebox.askyesno(
        "Blue Dot Agent — Firefox",
        "Для работы через Firefox нужна совместимая сборка Playwright.\n\n"
        "Скачать её сейчас? Загрузка — около 120 МБ, установка выполняется один раз.",
        parent=root,
    )
    if not accepted:
        root.destroy()
        raise RuntimeError("Загрузка Firefox отменена. Можно выбрать Google Chrome.")

    root.deiconify()
    root.title("Blue Dot Agent — загрузка Firefox")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frame = ttk.Frame(root, padding=20)
    frame.grid()
    ttk.Label(
        frame,
        text="Скачивается Firefox для Blue Dot Agent…",
    ).grid(row=0, column=0, sticky="w", pady=(0, 10))
    progress = ttk.Progressbar(frame, mode="indeterminate", length=360)
    progress.grid(row=1, column=0)
    progress.start(12)
    root.protocol("WM_DELETE_WINDOW", lambda: None)

    completed: queue.Queue[BaseException | None] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            install_firefox(cache)
        except BaseException as error:
            completed.put(error)
        else:
            completed.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def poll() -> None:
        try:
            result = completed.get_nowait()
        except queue.Empty:
            root.after(100, poll)
            return
        root._bluedot_result = result
        root.destroy()

    root.after(100, poll)
    root.after_idle(lambda: (root.lift(), root.focus_force()))
    root.mainloop()
    result = getattr(root, "_bluedot_result", None)
    if result is not None:
        raise result
