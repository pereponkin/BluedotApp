from __future__ import annotations

from typing import Any


_WINDOWS_V_KEYCODE = 86
_MAC_V_KEYCODE = 9


async def prompt_for_api_key(provider_label: str) -> str | None:
    """Ask for a secret outside the provider webpage's DOM."""

    return _prompt_for_api_key_sync(provider_label)


def _prompt_for_api_key_sync(provider_label: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError as error:
        raise OSError("Tkinter is unavailable") from error

    root = tk.Tk()
    root.withdraw()
    try:
        class ApiKeyDialog(simpledialog.Dialog):
            def body(self, master: Any) -> Any:
                self.attributes("-topmost", True)
                label = tk.Label(
                    master,
                    text=f"Введите API-ключ для {provider_label}:",
                    justify=tk.LEFT,
                )
                label.grid(row=0, padx=5, sticky=tk.W)
                self.entry = tk.Entry(master, name="entry", show="*", width=60)
                self.entry.grid(row=1, padx=5, sticky=tk.W + tk.E)
                self.entry.bind(
                    "<Control-KeyPress>",
                    lambda event: _paste_control_v(event, self.entry),
                    add=True,
                )
                self.entry.bind(
                    "<Command-KeyPress>",
                    lambda event: _paste_command_v(event, self.entry),
                    add=True,
                )
                self.after_idle(lambda: _activate_dialog(self, self.entry))
                return self.entry

            def apply(self) -> None:
                self.result = self.entry.get()

        dialog = ApiKeyDialog(root, "Blue Dot Agent — API-ключ")
        value = dialog.result
        return value.strip() if value and value.strip() else None
    finally:
        root.destroy()


def _activate_dialog(dialog: Any, entry: Any) -> None:
    dialog.attributes("-topmost", True)
    dialog.lift()
    dialog.focus_force()
    entry.focus_force()


def _paste_control_v(event: Any, entry: Any) -> str | None:
    if getattr(event, "keycode", None) != _WINDOWS_V_KEYCODE:
        return None
    entry.event_generate("<<Paste>>")
    return "break"


def _paste_command_v(event: Any, entry: Any) -> str | None:
    if getattr(event, "keycode", None) != _MAC_V_KEYCODE and getattr(
        event, "keysym", ""
    ) not in {"v", "V", "Cyrillic_em"}:
        return None
    entry.event_generate("<<Paste>>")
    return "break"
