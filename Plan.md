# Кроссплатформенный Blue Dot Agent без внешнего Python

## Цель

Один репозиторий выпускает автономные Windows x64, macOS Intel и macOS Apple Silicon пакеты. Пользователь не устанавливает Python или зависимости, выбирает загружаемый по требованию Playwright Firefox либо системный Google Chrome и получает одинаковую панель поиска и скачивания.

## Реализованный контракт

- Настройки версии 2 содержат `browser = firefox | chrome`; версия 1 мигрирует в Firefox.
- Приоритет: `--browser` → `BLUEDOT_BROWSER` → сохранённое значение → системное окно первого запуска.
- Браузеры не входят в PyInstaller-пакет. Chrome запускается через `channel="chrome"`; совместимый Firefox скачивается Playwright только при первом выборе в отдельный кэш данных агента.
- Firefox и Chrome используют отдельные профили. Старый Windows Firefox-профиль сохраняется.
- Выбор браузера доступен под шестерёнкой и применяется после следующего запуска.
- Данные: `%LOCALAPPDATA%\BlueDotAgent` на Windows и `~/Library/Application Support/BlueDotAgent` на macOS.
- Секреты: Windows DPAPI и macOS Keychain; DOM и обычный JSON получают только признак наличия ключа.
- Один Python-entrypoint выполняет выбор браузера, проверку Chrome, межпроцессную блокировку, запуск панели и отображение ошибок.
- `Ctrl+V` и `Cmd+V`, загрузки, открытие файла и системные ошибки работают платформенно.
- YAML, `panel.js` и справка загружаются как package resources.
- `--self-test` проверяет ресурсы, запись в папку данных, защищённое хранилище и доступность выбранного браузера без аккаунта и API-ключа. До ленивой установки Firefox допустим статус `download_required`.

## Выпуск

- Windows: PyInstaller `onedir/windowed`, portable ZIP и Inno Setup installer.
- macOS: отдельные `.app` на `macos-15-intel` и `macos-15`, ad-hoc подпись, ZIP и инструкции Gatekeeper.
- CI: Windows/macOS, Python 3.11, pytest, `node --check`, панель в Firefox и Chromium, smoke системного Chrome.
- Release: ручной запуск или тег `v*`, распаковка финального архива вне checkout, обязательный frozen self-test, четыре пакета и `SHA256SUMS.txt`.

## Приёмка

Автоматически проверяются миграция настроек, платформенные пути, приоритет браузера, раздельные профили, Keychain/DPAPI, блокировка экземпляра, package resources, Firefox/Chromium UI и конфигурация release.

Перед выпуском вручную проверяется матрица Windows/macOS Intel/macOS ARM64 × Firefox/Chrome: вход, API-ключ, поиск, история, масштабирование, воспроизведение, скачивание, повторный запуск и защита профиля.

Не входят: Linux, Safari, Edge, автообновление, личный профиль браузера, Apple Developer Program и нотариализация.
