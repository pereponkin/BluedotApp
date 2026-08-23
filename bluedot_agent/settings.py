from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .config import STATE_DIR
from .browser import BROWSER_KINDS, BrowserKind
from .downloads import default_download_directory as system_default_download_directory


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    default_model: str
    recommended_models: tuple[str, ...]
    api_key_environment_variable: str


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        id="gemini",
        label="Google AI Studio (Gemini)",
        default_model="gemini-3.5-flash-lite",
        recommended_models=("gemini-3.5-flash-lite", "gemini-3.5-flash"),
        api_key_environment_variable="GEMINI_API_KEY",
    ),
    "groq": ProviderSpec(
        id="groq",
        label="Groq",
        default_model="openai/gpt-oss-120b",
        recommended_models=("openai/gpt-oss-120b", "openai/gpt-oss-20b"),
        api_key_environment_variable="GROQ_API_KEY",
    ),
    "openrouter": ProviderSpec(
        id="openrouter",
        label="OpenRouter",
        default_model="openai/gpt-oss-20b:free",
        recommended_models=("openai/gpt-oss-20b:free",),
        api_key_environment_variable="OPENROUTER_API_KEY",
    ),
    "mistral": ProviderSpec(
        id="mistral",
        label="Mistral",
        default_model="mistral-small-latest",
        recommended_models=("mistral-small-latest", "ministral-8b-latest"),
        api_key_environment_variable="MISTRAL_API_KEY",
    ),
}

_RETIRED_PROVIDER_IDS = {"cerebras"}
_RETIRED_MODELS = {
    ("openrouter", "openai/gpt-oss-120b:free"): "openai/gpt-oss-20b:free",
}
LANGUAGES = frozenset({"ru", "en"})


@dataclass(frozen=True)
class ProviderCredentials:
    provider: str
    model: str
    api_key: str


class ProviderConfigurationError(RuntimeError):
    pass


class SecretProtector(Protocol):
    def protect(self, value: bytes) -> bytes: ...

    def unprotect(self, value: bytes) -> bytes: ...


class ApiKeyStore(Protocol):
    def has(self, provider: str) -> bool: ...

    def get(self, provider: str) -> str | None: ...

    def set(self, provider: str, value: str) -> None: ...

    def delete(self, provider: str) -> None: ...


class MacKeychainBackend(Protocol):
    def get(self, account: str) -> str | None: ...

    def set(self, account: str, value: str) -> None: ...

    def delete(self, account: str) -> None: ...


class MacKeychainStore:
    """Store provider API keys in the current macOS user's Keychain."""

    def __init__(self, *, backend: MacKeychainBackend | None = None) -> None:
        self._backend = backend or _SecurityFrameworkKeychain()

    def has(self, provider: str) -> bool:
        return self.get(provider) is not None

    def get(self, provider: str) -> str | None:
        return self._backend.get(provider)

    def set(self, provider: str, value: str) -> None:
        self._backend.set(provider, value)

    def delete(self, provider: str) -> None:
        self._backend.delete(provider)


class _SecurityFrameworkKeychain:
    """Minimal Security.framework binding that never exposes secrets in argv."""

    _SERVICE = b"BlueDotAgent"
    _ITEM_NOT_FOUND = -25300

    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise OSError("macOS Keychain is only available on macOS")
        self._security = ctypes.CDLL(
            "/System/Library/Frameworks/Security.framework/Security"
        )
        self._core_foundation = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        pointer = ctypes.c_void_p
        self._security.SecKeychainFindGenericPassword.argtypes = [
            pointer,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(pointer),
            ctypes.POINTER(pointer),
        ]
        self._security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
        self._security.SecKeychainAddGenericPassword.argtypes = [
            pointer,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.POINTER(pointer),
        ]
        self._security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
        self._security.SecKeychainItemModifyAttributesAndData.argtypes = [
            pointer,
            pointer,
            ctypes.c_uint32,
            ctypes.c_char_p,
        ]
        self._security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
        self._security.SecKeychainItemDelete.argtypes = [pointer]
        self._security.SecKeychainItemDelete.restype = ctypes.c_int32
        self._security.SecKeychainItemFreeContent.argtypes = [pointer, pointer]
        self._security.SecKeychainItemFreeContent.restype = ctypes.c_int32
        self._core_foundation.CFRelease.argtypes = [pointer]

    @staticmethod
    def _bytes(value: str) -> bytes:
        return value.encode("utf-8")

    def _find(self, account: str) -> tuple[int, ctypes.c_void_p, ctypes.c_void_p, int]:
        account_bytes = self._bytes(account)
        data_length = ctypes.c_uint32()
        data = ctypes.c_void_p()
        item = ctypes.c_void_p()
        status = self._security.SecKeychainFindGenericPassword(
            None,
            len(self._SERVICE),
            self._SERVICE,
            len(account_bytes),
            account_bytes,
            ctypes.byref(data_length),
            ctypes.byref(data),
            ctypes.byref(item),
        )
        return status, data, item, data_length.value

    def get(self, account: str) -> str | None:
        status, data, item, length = self._find(account)
        if status == self._ITEM_NOT_FOUND:
            return None
        self._check(status)
        try:
            return ctypes.string_at(data, length).decode("utf-8")
        finally:
            self._security.SecKeychainItemFreeContent(None, data)
            self._core_foundation.CFRelease(item)

    def set(self, account: str, value: str) -> None:
        status, data, item, _ = self._find(account)
        value_bytes = self._bytes(value)
        if status == 0:
            self._security.SecKeychainItemFreeContent(None, data)
            try:
                self._check(
                    self._security.SecKeychainItemModifyAttributesAndData(
                        item,
                        None,
                        len(value_bytes),
                        value_bytes,
                    )
                )
            finally:
                self._core_foundation.CFRelease(item)
            return
        if status != self._ITEM_NOT_FOUND:
            self._check(status)
        account_bytes = self._bytes(account)
        self._check(
            self._security.SecKeychainAddGenericPassword(
                None,
                len(self._SERVICE),
                self._SERVICE,
                len(account_bytes),
                account_bytes,
                len(value_bytes),
                value_bytes,
                None,
            )
        )

    def delete(self, account: str) -> None:
        status, data, item, _ = self._find(account)
        if status == self._ITEM_NOT_FOUND:
            return
        self._check(status)
        self._security.SecKeychainItemFreeContent(None, data)
        try:
            self._check(self._security.SecKeychainItemDelete(item))
        finally:
            self._core_foundation.CFRelease(item)

    @staticmethod
    def _check(status: int) -> None:
        if status != 0:
            raise OSError(f"macOS Keychain error: {status}")


class WindowsDataProtector:
    """Encrypt secrets for the current Windows user through DPAPI."""

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    class _DataBlob(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.c_ulong),
            ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
        ]

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows DPAPI is only available on Windows")
        self._crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    @classmethod
    def _blob(cls, value: bytes) -> tuple[_DataBlob, Any]:
        buffer = ctypes.create_string_buffer(value)
        blob = cls._DataBlob(
            len(value),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        return blob, buffer

    def protect(self, value: bytes) -> bytes:
        source, source_buffer = self._blob(value)
        destination = self._DataBlob()
        result = self._crypt32.CryptProtectData(
            ctypes.byref(source),
            "Blue Dot Agent API key",
            None,
            None,
            None,
            self._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(destination),
        )
        del source_buffer
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            self._kernel32.LocalFree(destination.pbData)

    def unprotect(self, value: bytes) -> bytes:
        source, source_buffer = self._blob(value)
        destination = self._DataBlob()
        result = self._crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            self._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(destination),
        )
        del source_buffer
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            self._kernel32.LocalFree(destination.pbData)


class ProviderSettingsStore:
    def __init__(
        self,
        *,
        path: Path | None = None,
        protector: SecretProtector | None = None,
        secret_store: ApiKeyStore | None = None,
        environ: Mapping[str, str] | None = None,
        default_download_directory: Callable[[], Path] | None = None,
    ) -> None:
        self._path = path or STATE_DIR / "settings.json"
        self._secret_store = secret_store or (
            MacKeychainStore() if protector is None and sys.platform == "darwin" else None
        )
        self._protector = protector or (
            WindowsDataProtector() if self._secret_store is None else None
        )
        self._environ = environ if environ is not None else os.environ
        self._default_download_directory = (
            default_download_directory or system_default_download_directory
        )

    def public_state(self) -> dict[str, Any]:
        settings = self._load()
        selected_provider = settings["selected_provider"]
        saved_providers = settings["providers"]
        providers: dict[str, dict[str, Any]] = {}
        for provider_id, spec in PROVIDER_SPECS.items():
            saved = saved_providers.get(provider_id, {})
            providers[provider_id] = {
                "id": spec.id,
                "label": spec.label,
                "model": saved.get("model", spec.default_model),
                "recommended_models": list(spec.recommended_models),
                "has_api_key": bool(
                    (self._secret_store and self._secret_store.has(provider_id))
                    or saved.get("protected_api_key")
                    or self._environment_key(spec)
                ),
            }
        return {
            "browser": settings["browser"],
            "language": settings["language"],
            "selected_provider": selected_provider,
            "providers": providers,
            "download_directory": str(self.download_directory()),
        }

    def has_saved_browser(self) -> bool:
        if not self._path.exists():
            return False
        self._load()
        return True

    def browser(self) -> BrowserKind:
        return self._load()["browser"]

    def language(self) -> str:
        return self._load()["language"]

    def save_browser(self, browser: str) -> BrowserKind:
        normalized = browser.strip().casefold()
        if normalized not in BROWSER_KINDS:
            raise ProviderConfigurationError("Неизвестный браузер.")
        settings = self._load()
        settings["browser"] = normalized
        self._write(settings)
        return normalized

    def save_language(self, language: str) -> dict[str, Any]:
        normalized = language.strip().casefold()
        if normalized not in LANGUAGES:
            raise ProviderConfigurationError("Неизвестный язык интерфейса.")
        settings = self._load()
        settings["language"] = normalized
        self._write(settings)
        return self.public_state()

    def download_directory(self) -> Path:
        environment_value = self._environ.get("BLUEDOT_DOWNLOAD_DIR", "").strip()
        if environment_value:
            return Path(os.path.expandvars(environment_value))
        saved_value = self._load().get("download_directory")
        if isinstance(saved_value, str) and saved_value:
            return Path(saved_value)
        return self._default_download_directory()

    def credentials(self) -> ProviderCredentials:
        settings = self._load()
        provider_id = settings["selected_provider"]
        spec = PROVIDER_SPECS[provider_id]
        saved = settings["providers"].get(provider_id, {})
        model = str(saved.get("model", spec.default_model)).strip()
        api_key = ""
        if self._secret_store is not None:
            api_key = self._secret_store.get(provider_id) or ""
        protected = saved.get("protected_api_key") if not api_key else None
        if isinstance(protected, str) and protected and self._protector is not None:
            try:
                encrypted = base64.b64decode(protected, validate=True)
                api_key = self._protector.unprotect(encrypted).decode("utf-8")
            except (ValueError, UnicodeError, OSError) as error:
                raise ProviderConfigurationError(
                    "Не удалось прочитать сохранённый API-ключ."
                ) from error
        if not api_key:
            api_key = self._environment_key(spec)
        if not api_key:
            raise ProviderConfigurationError(
                f"API-ключ для {spec.label} не настроен."
            )
        return ProviderCredentials(provider_id, model, api_key)

    def save(
        self,
        *,
        provider: str,
        model: str,
        api_key: str | None = None,
        clear_api_key: bool = False,
        download_directory: str | None = None,
        browser: str | None = None,
    ) -> dict[str, Any]:
        provider_id = provider.strip().casefold()
        if provider_id not in PROVIDER_SPECS:
            raise ProviderConfigurationError("Неизвестный провайдер.")
        normalized_model = model.strip()
        if not normalized_model:
            raise ProviderConfigurationError("Укажите модель.")

        settings = self._load()
        saved = dict(settings["providers"].get(provider_id, {}))
        saved["model"] = normalized_model
        if clear_api_key:
            if self._secret_store is not None:
                self._secret_store.delete(provider_id)
            saved.pop("protected_api_key", None)
        elif api_key is not None and api_key.strip():
            if self._secret_store is not None:
                self._secret_store.set(provider_id, api_key.strip())
                saved.pop("protected_api_key", None)
            elif self._protector is not None:
                encrypted = self._protector.protect(api_key.strip().encode("utf-8"))
                saved["protected_api_key"] = base64.b64encode(encrypted).decode("ascii")

        settings["selected_provider"] = provider_id
        settings["providers"][provider_id] = saved
        if browser is not None:
            normalized_browser = browser.strip().casefold()
            if normalized_browser not in BROWSER_KINDS:
                raise ProviderConfigurationError("Неизвестный браузер.")
            settings["browser"] = normalized_browser
        if download_directory is not None:
            expanded_directory = Path(
                os.path.expandvars(download_directory.strip())
            ).expanduser()
            if not download_directory.strip() or not expanded_directory.is_absolute():
                raise ProviderConfigurationError(
                    "Укажите полный путь к папке для скачивания."
                )
            settings["download_directory"] = str(expanded_directory)
        self._write(settings)
        return self.public_state()

    def _environment_key(self, spec: ProviderSpec) -> str:
        return self._environ.get(spec.api_key_environment_variable, "").strip()

    def _load(self) -> dict[str, Any]:
        default = {
            "version": 2,
            "browser": "firefox",
            "language": "ru",
            "selected_provider": "gemini",
            "providers": {},
        }
        if not self._path.exists():
            return default
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProviderConfigurationError(
                "Файл настроек помощника повреждён."
            ) from error
        if not isinstance(loaded, dict):
            raise ProviderConfigurationError(
                "Файл настроек помощника повреждён."
            )
        selected = loaded.get("selected_provider", "gemini")
        providers = loaded.get("providers", {})
        if not isinstance(providers, dict):
            raise ProviderConfigurationError(
                "Файл настроек помощника повреждён."
            )
        version = loaded.get("version", 1)
        browser = loaded.get("browser", "firefox")
        language = loaded.get("language", "ru")
        if (
            version not in (1, 2)
            or browser not in BROWSER_KINDS
            or language not in LANGUAGES
        ):
            raise ProviderConfigurationError(
                "Файл настроек помощника повреждён."
            )
        needs_migration = (
            version != 2
            or "language" not in loaded
            or selected in _RETIRED_PROVIDER_IDS
            or any(provider_id in _RETIRED_PROVIDER_IDS for provider_id in providers)
        )
        if selected in _RETIRED_PROVIDER_IDS:
            selected = "gemini"
        elif selected not in PROVIDER_SPECS:
            raise ProviderConfigurationError(
                "Файл настроек помощника повреждён."
            )
        if any(
            (
                provider_id not in PROVIDER_SPECS
                and provider_id not in _RETIRED_PROVIDER_IDS
            )
            or not isinstance(values, dict)
            for provider_id, values in providers.items()
        ):
            raise ProviderConfigurationError(
                "Файл настроек помощника повреждён."
            )
        normalized_providers = {
            provider_id: dict(values)
            for provider_id, values in providers.items()
            if provider_id not in _RETIRED_PROVIDER_IDS
        }
        for provider_id, values in normalized_providers.items():
            model = values.get("model")
            replacement = _RETIRED_MODELS.get((provider_id, model))
            if replacement is not None:
                values["model"] = replacement
                needs_migration = True
        normalized = {
            "version": 2,
            "browser": browser,
            "language": language,
            "selected_provider": selected,
            "providers": normalized_providers,
        }
        download_directory = loaded.get("download_directory")
        if download_directory is not None:
            if not isinstance(download_directory, str) or not download_directory.strip():
                raise ProviderConfigurationError(
                    "Файл настроек помощника повреждён."
                )
            normalized["download_directory"] = download_directory
        if needs_migration:
            self._write(normalized)
        return normalized

    def _write(self, settings: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self._path)
