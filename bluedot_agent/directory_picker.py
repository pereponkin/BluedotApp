from __future__ import annotations

from pathlib import Path

from .secret_prompt import _activate_dialog


async def choose_download_directory(
    initial_directory: Path,
    language: str = "ru",
) -> Path | None:
    """Open the system folder picker outside the Blue Dot page DOM."""

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as error:
        raise OSError("Tkinter is unavailable") from error

    if initial_directory.is_dir():
        initial = initial_directory
    else:
        initial = initial_directory.parent
        if not initial.is_dir():
            initial = Path.home()

    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise OSError("The system folder picker is unavailable") from error
    root.withdraw()
    try:
        root.update_idletasks()
        _activate_dialog(root, root)
        try:
            selected = filedialog.askdirectory(
                parent=root,
                title=(
                    "Blue Dot Agent — download folder"
                    if language == "en"
                    else "Blue Dot Agent — папка для скачивания"
                ),
                initialdir=str(initial),
                mustexist=True,
            )
        except tk.TclError as error:
            raise OSError("The system folder picker failed") from error
        return Path(selected) if selected else None
    finally:
        root.destroy()
