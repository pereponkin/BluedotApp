from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

from .config import LEGACY_PROFILE_DIR, PROFILE_DIR, STATE_DIR


BrowserKind = Literal["firefox", "chrome"]
BROWSER_KINDS: tuple[BrowserKind, ...] = ("firefox", "chrome")


PROFILE_CACHE_NAMES = {
    "cache2",
    "startupCache",
    "shader-cache",
    "storage-sync-v2.sqlite",
    "parent.lock",
}


def profile_dir_for(
    browser: BrowserKind,
    *,
    state_dir: Path = STATE_DIR,
    profile_override: Path | None = None,
) -> Path:
    if profile_override is not None:
        return profile_override
    return state_dir / ("profile" if browser == "firefox" else "profile-chrome")


def prepare_profile_dir(
    profile_dir: Path = PROFILE_DIR,
    legacy_profile_dir: Path = LEGACY_PROFILE_DIR,
) -> bool:
    profile_dir = profile_dir.resolve()
    legacy_profile_dir = legacy_profile_dir.resolve()
    if profile_dir.exists():
        profile_dir.mkdir(parents=True, exist_ok=True)
        return False
    profile_dir.parent.mkdir(parents=True, exist_ok=True)
    if not legacy_profile_dir.exists() or profile_dir == legacy_profile_dir:
        profile_dir.mkdir(parents=True, exist_ok=True)
        return False

    shutil.copytree(
        legacy_profile_dir,
        profile_dir,
        ignore=shutil.ignore_patterns(*PROFILE_CACHE_NAMES),
    )
    return True


async def launch_context(
    playwright: Any,
    profile_dir: Path,
    *,
    headed: bool,
    browser: BrowserKind = "firefox",
    legacy_profile_dir: Path = LEGACY_PROFILE_DIR,
) -> Any:
    if browser == "firefox":
        prepare_profile_dir(profile_dir, legacy_profile_dir)
    else:
        profile_dir.mkdir(parents=True, exist_ok=True)
    viewport_options = (
        {"no_viewport": True}
        if headed
        else {"viewport": {"width": 1280, "height": 900}}
    )
    options = {
        "user_data_dir": str(profile_dir),
        "headless": not headed,
        "accept_downloads": True,
        **viewport_options,
    }
    if browser == "chrome":
        return await playwright.chromium.launch_persistent_context(
            channel="chrome",
            **options,
        )
    return await playwright.firefox.launch_persistent_context(
        firefox_user_prefs={
            "browser.cache.disk.capacity": 102400,
            "browser.cache.disk.smart_size.enabled": False,
        },
        **options,
    )
