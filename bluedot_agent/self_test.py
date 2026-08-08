from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from playwright._impl._driver import compute_driver_executable

from .browser import BROWSER_KINDS, BrowserKind
from .browser_install import configure_browser_cache, firefox_is_installed
from .config import STATE_DIR, load_yaml
from .launcher import chrome_is_available
from .settings import MacKeychainStore, WindowsDataProtector


def _launch_browser(browser: BrowserKind) -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser_type = playwright.firefox if browser == "firefox" else playwright.chromium
            options = {"channel": "chrome"} if browser == "chrome" else {}
            launched = browser_type.launch(headless=True, **options)
            launched.close()
            return True
    except Exception:
        return False


def browser_readiness(browser: BrowserKind) -> tuple[bool, str]:
    configure_browser_cache()
    if browser == "chrome":
        if not chrome_is_available():
            return False, "missing"
        return _launch_browser("chrome"), "ready"
    if firefox_is_installed():
        return _launch_browser("firefox"), "ready"
    executable, cli = compute_driver_executable()
    if Path(executable).is_file() and Path(cli).is_file():
        return True, "download_required"
    return False, "installer_missing"


def _state_directory_writable() -> bool:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=STATE_DIR, prefix="self-test-", delete=True):
            return True
    except OSError:
        return False


def _secret_storage_available() -> bool:
    if sys.platform == "win32":
        try:
            protector = WindowsDataProtector()
            sample = os.urandom(32)
            return protector.unprotect(protector.protect(sample)) == sample
        except OSError:
            return False
    if sys.platform == "darwin":
        account = f"self-test-{uuid4().hex}"
        value = uuid4().hex
        store = None
        try:
            store = MacKeychainStore()
            store.set(account, value)
            return store.get(account) == value
        except OSError:
            return False
        finally:
            if store is not None:
                try:
                    store.delete(account)
                except OSError:
                    pass
    return False


def run_self_test(
    *,
    browser: str | None = None,
    require_frozen: bool = False,
) -> dict[str, Any]:
    selected_value = "firefox" if browser is None else browser
    selected: BrowserKind = (
        selected_value if selected_value in BROWSER_KINDS else "firefox"
    )
    checks: dict[str, bool] = {}
    try:
        inventory = load_yaml("provider_inventory.yaml")
        rules = load_yaml("mapping_rules.yaml")
        checks["resources"] = bool(inventory.get("providers") and rules.get("presets"))
    except (OSError, ValueError):
        checks["resources"] = False
    checks["state_directory"] = _state_directory_writable()
    checks["secret_storage"] = _secret_storage_available()
    browser_ok, browser_status = browser_readiness(selected)
    checks["browser"] = selected_value in BROWSER_KINDS and browser_ok
    frozen = bool(getattr(sys, "frozen", False))
    checks["frozen_runtime"] = frozen or not require_frozen
    return {
        "ok": all(checks.values()),
        "frozen": frozen,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "browser": selected,
        "browser_status": browser_status,
        "state_directory": str(STATE_DIR),
        "checks": checks,
    }


def print_self_test(result: dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))
