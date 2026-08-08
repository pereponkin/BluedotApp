from __future__ import annotations

import sys
import subprocess


APP_TITLE = "Blue Dot Agent"
# MB_OK | MB_ICONERROR | MB_TOPMOST
_MESSAGE_BOX_ERROR = 0x00000000 | 0x00000010 | 0x00040000


def report_failure(lines: list[str], *, title: str = APP_TITLE) -> None:
    """Show a failure where the user can actually see it.

    A windowed packaged app has no console, so ``sys.stdout`` is ``None``.
    In that mode the message goes to a native system dialog instead.

    Args:
        lines (list): Message lines, shown in order.
        title (str, optional): Window caption used when no console is attached.
    """
    if sys.stdout is not None:
        for line in lines:
            print(line)
        return
    _show_message_box(title, "\n".join(lines))


def _show_message_box(title: str, text: str) -> None:
    if sys.platform == "darwin":
        script = (
            "display dialog "
            + _apple_script_string(text)
            + " with title "
            + _apple_script_string(title)
            + ' buttons {"OK"} default button "OK" with icon stop'
        )
        subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            check=False,
            capture_output=True,
        )
        return
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.user32.MessageBoxW(None, text, title, _MESSAGE_BOX_ERROR)


def _apple_script_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
