# Release notes

Blue Dot Agent поставляется с Python и зависимостями, но без браузеров. Google Chrome используется из системы. Совместимый Playwright Firefox скачивается только при первом выборе Firefox (около 120 МБ), поэтому пользователи Chrome не получают лишний большой файл.

Windows- и macOS-пакеты не подписаны коммерческими сертификатами. SmartScreen и Gatekeeper могут показать предупреждение. Сверьте файл с `SHA256SUMS.txt`, затем используйте инструкции первого запуска из README. На macOS откройте `System Settings → Privacy & Security → Open Anyway → Open`; не отключайте Gatekeeper целиком.

API-ключи и данные пользователя не входят в пакет и не переносятся через GitHub Actions.
