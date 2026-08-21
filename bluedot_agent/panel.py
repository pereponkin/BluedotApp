from __future__ import annotations

import json
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .help_content import help_document
from .intent import (
    BlueDotIntent,
    ProviderUnavailableError,
    selectable_filters,
)
from .secret_prompt import prompt_for_api_key
from .settings import (
    PROVIDER_SPECS,
    ProviderConfigurationError,
    ProviderSettingsStore,
)


MAX_PROMPT_LENGTH = 1000
PANEL_BINDING_NAME = "__bluedotPanelCommand"
BASELINE_HISTORY_INDEX = -1


@dataclass(frozen=True)
class PanelFilterSnapshot:
    """Exact Blue Dot filter payload of a single panel search."""

    range_filters: list[dict[str, Any]] = field(default_factory=list)
    selectable_filters: list[dict[str, str]] = field(default_factory=list)
    requested_sliders: dict[str, tuple[int, int]] = field(default_factory=dict)

    def filter_names(self) -> list[str]:
        names = [str(item["filterName"]) for item in self.range_filters]
        names.extend(str(item["filterName"]) for item in self.selectable_filters)
        return names


PANEL_SCRIPT = resources.files(__package__) / "panel.js"


class PanelHandler:
    def __init__(
        self,
        mapper: Any,
        search: Callable[[BlueDotIntent], Awaitable[dict[str, Any]]],
        settings: ProviderSettingsStore | None = None,
        api_key_prompt: Callable[[str], Awaitable[str | None]] = prompt_for_api_key,
        directory_picker: Callable[[Path], Awaitable[Path | None]] | None = None,
        download_directory_changed: Callable[[Path], None] | None = None,
        open_download: Callable[[], bool] | None = None,
        restore: Callable[[PanelFilterSnapshot], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        self._mapper = mapper
        self._search = search
        self._settings = settings
        self._api_key_prompt = api_key_prompt
        self._directory_picker = directory_picker
        self._download_directory_changed = download_directory_changed
        self._open_download = open_download
        self._restore = restore
        self._history: list[dict[str, Any]] = []
        self._busy = False
        self._settings_busy = False

    async def __call__(self, source: dict[str, Any], command: dict[str, Any]) -> dict[str, Any]:
        frame = source.get("frame") if isinstance(source, dict) else None
        frame_url = getattr(frame, "url", "")
        if urlsplit(frame_url).hostname != "app.sessions.blue":
            return _error("Команда недоступна для этой страницы.")
        if not isinstance(command, dict):
            return _error("Неизвестная команда панели.")
        command_type = command.get("type")
        if command_type == "get_settings":
            if self._settings is None:
                return _error("Настройки недоступны.")
            try:
                return {"ok": True, "settings": self._settings.public_state()}
            except ProviderConfigurationError as error:
                return _error(str(error))
        if command_type == "save_settings":
            return self._save_settings(command)
        if command_type == "set_api_key":
            return await self._set_api_key(command)
        if command_type == "choose_download_directory":
            return await self._choose_download_directory(command)
        if command_type == "open_download":
            try:
                opened = self._open_download is not None and self._open_download()
            except OSError:
                return _error("Не удалось открыть скачанный файл.")
            if not opened:
                return _error("Скачанный файл больше недоступен.")
            return {"ok": True}
        if command_type == "restore":
            return await self._restore_history_entry(command)
        if command_type != "search":
            return _error("Неизвестная команда панели.")
        raw_prompt = command.get("prompt")
        if not isinstance(raw_prompt, str):
            return _error("Введите текстовый запрос.")
        prompt = raw_prompt.strip()
        if not prompt:
            return _error("Введите текстовый запрос.")
        if len(prompt) > MAX_PROMPT_LENGTH:
            return _error(f"Запрос не должен превышать {MAX_PROMPT_LENGTH} символов.")
        if self._busy:
            return _error("Поиск уже выполняется.")
        self._busy = True
        try:
            intent = self._mapper.map_prompt(prompt, preset_name="auto")
            state = await self._search(intent)
            result = {
                "ok": True,
                "prompt": prompt,
                "parser": intent.preset_name,
                "warning": self._mapper.last_warning,
                "applied_sliders": _serializable_ranges(state["applied_sliders"]),
                "categories": selectable_filters(intent),
                "missing_sliders": _serializable_ranges(state["missing_sliders"]),
                "exact_count": state["exact_count"],
                "has_related": state["has_related"],
            }
            snapshot = state.get("snapshot")
            if isinstance(snapshot, PanelFilterSnapshot) and self._restore is not None:
                self._history.append({"snapshot": snapshot, "result": result})
                result = {**result, "history_index": len(self._history) - 1}
            return result
        except ProviderUnavailableError as error:
            return _error(str(error))
        except Exception as error:
            return _error(f"Не удалось выполнить поиск ({type(error).__name__}).")
        finally:
            self._busy = False

    async def _restore_history_entry(self, command: dict[str, Any]) -> dict[str, Any]:
        if self._restore is None:
            return _error("История поисков недоступна.")
        index = command.get("index")
        if not isinstance(index, int) or isinstance(index, bool):
            return _error("Некорректная запись истории.")
        if index != BASELINE_HISTORY_INDEX and not 0 <= index < len(self._history):
            return _error("Эта запись истории больше недоступна.")
        if self._busy:
            return _error("Поиск уже выполняется.")
        self._busy = True
        try:
            entry = None if index == BASELINE_HISTORY_INDEX else self._history[index]
            snapshot = PanelFilterSnapshot() if entry is None else entry["snapshot"]
            state = await self._restore(snapshot)
            if entry is None:
                return {"ok": True, "result": None}
            return {
                "ok": True,
                "result": {
                    **entry["result"],
                    "applied_sliders": _serializable_ranges(state["applied_sliders"]),
                    "missing_sliders": _serializable_ranges(state["missing_sliders"]),
                    "exact_count": state["exact_count"],
                    "has_related": state["has_related"],
                },
            }
        except Exception as error:
            return _error(f"Не удалось вернуть прошлый запрос ({type(error).__name__}).")
        finally:
            self._busy = False

    def _save_settings(self, command: dict[str, Any]) -> dict[str, Any]:
        if self._settings is None:
            return _error("Настройки недоступны.")
        provider = command.get("provider")
        model = command.get("model")
        api_key = command.get("api_key")
        clear_api_key = command.get("clear_api_key", False)
        download_directory = command.get("download_directory")
        browser = command.get("browser")
        if not isinstance(provider, str) or not isinstance(model, str):
            return _error("Провайдер и модель должны быть текстом.")
        if api_key is not None:
            return _error("API-ключ вводится только в защищённом окне.")
        if not isinstance(clear_api_key, bool):
            return _error("Некорректная команда удаления API-ключа.")
        if download_directory is not None and not isinstance(download_directory, str):
            return _error("Папка для скачивания должна быть текстом.")
        if browser is not None and not isinstance(browser, str):
            return _error("Браузер должен быть текстом.")
        try:
            save_values = {
                "provider": provider,
                "model": model,
                "clear_api_key": clear_api_key,
            }
            if download_directory is not None:
                save_values["download_directory"] = download_directory
            if browser is not None:
                save_values["browser"] = browser
            settings = self._settings.save(
                **save_values,
            )
            if (
                download_directory is not None
                and self._download_directory_changed is not None
            ):
                self._download_directory_changed(
                    Path(settings["download_directory"])
                )
            return {"ok": True, "settings": settings}
        except ProviderConfigurationError as error:
            return _error(str(error))
        except (OSError, UnicodeError):
            return _error("Не удалось сохранить настройки.")

    async def _set_api_key(self, command: dict[str, Any]) -> dict[str, Any]:
        if self._settings is None:
            return _error("Настройки недоступны.")
        provider = command.get("provider")
        model = command.get("model")
        if not isinstance(provider, str) or not isinstance(model, str):
            return _error("Провайдер и модель должны быть текстом.")
        provider_id = provider.strip().casefold()
        spec = PROVIDER_SPECS.get(provider_id)
        if spec is None:
            return _error("Неизвестный провайдер.")
        if not model.strip():
            return _error("Укажите модель.")
        if self._settings_busy:
            return _error("Окно API-ключа уже открыто.")
        self._settings_busy = True
        try:
            api_key = await self._api_key_prompt(spec.label)
            if not api_key:
                return _error("Ввод API-ключа отменён.")
            settings = self._settings.save(
                provider=provider_id,
                model=model,
                api_key=api_key,
            )
            return {"ok": True, "settings": settings}
        except (ProviderConfigurationError, OSError, UnicodeError):
            return _error("Не удалось сохранить API-ключ.")
        finally:
            self._settings_busy = False

    async def _choose_download_directory(
        self, command: dict[str, Any]
    ) -> dict[str, Any]:
        raw_directory = command.get("download_directory")
        if not isinstance(raw_directory, str) or not raw_directory.strip():
            return _error("Не удалось определить текущую папку для скачивания.")
        if self._directory_picker is None:
            return _error("Системный выбор папки недоступен.")
        if self._settings_busy:
            return _error("Другое окно настроек уже открыто.")
        self._settings_busy = True
        try:
            selected = await self._directory_picker(Path(raw_directory.strip()))
            if selected is None:
                return {"ok": True, "cancelled": True}
            return {"ok": True, "download_directory": str(selected)}
        except (OSError, RuntimeError, UnicodeError):
            return _error("Не удалось открыть системный выбор папки.")
        finally:
            self._settings_busy = False


def panel_init_script(run_id: str) -> str:
    """Return the panel bootstrap script with its placeholders filled in.

    Args:
        run_id (str): Identifier isolating this run's session storage.

    Returns:
        (str)
    """
    source = PANEL_SCRIPT.read_text(encoding="utf-8")
    return source.replace("__BLUEDOT_PANEL_RUN_ID__", run_id).replace(
        "__BLUEDOT_HELP_CONTENT__", json.dumps(help_document())
    )


async def install_panel(page: Any, handler: PanelHandler) -> None:
    await page.expose_binding(PANEL_BINDING_NAME, handler)
    await page.add_init_script(panel_init_script(secrets.token_hex(16)))


def _serializable_ranges(ranges: dict[str, tuple[int, int]]) -> dict[str, list[int]]:
    return {name: [value[0], value[1]] for name, value in ranges.items()}


def _error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}
