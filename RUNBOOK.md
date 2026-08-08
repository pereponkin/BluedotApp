# Blue Dot Agent Runbook

## Обычный запуск

Пользователь запускает автономный `BlueDotAgent.exe` на Windows или `BlueDotAgent.app` на macOS. Разработчик может запустить ту же точку входа из репозитория:

```text
python -m bluedot_agent --browser firefox panel
python -m bluedot_agent --browser chrome panel
```

При первом выборе Firefox агент предлагает скачать совместимую сборку Playwright. Chrome должен быть установлен в системе. Оба браузера используют отдельные агентские профили; личные профили пользователя не затрагиваются.

Каждый поиск заменяет прежний GraphQL gate и одним обновлением передаёт все фильтры в React-контекст Blue Dot. Пагинация и последующие ручные изменения остаются рабочими. При нуле точных результатов автоматического расширяющего поиска нет; похожие треки Blue Dot остаются доступны.

## Данные

| Назначение | Windows | macOS |
|---|---|---|
| Состояние агента | `%LOCALAPPDATA%\BlueDotAgent` | `~/Library/Application Support/BlueDotAgent` |
| Firefox-профиль | `profile` | `profile` |
| Chrome-профиль | `profile-chrome` | `profile-chrome` |
| Кэш Playwright Firefox | `browsers` | `browsers` |
| API-ключи | DPAPI текущего пользователя | системный Keychain |
| Диагностика | `logs` | `logs` |
| Блокировка экземпляра | `agent.lock` | `agent.lock` |

Пути разрешается переопределять переменными `BLUEDOT_STATE_DIR`, `BLUEDOT_PROFILE_DIR`, `BLUEDOT_LOG_DIR` и `BLUEDOT_DOWNLOAD_DIR`.

Если запуск сообщает о втором экземпляре, закройте уже открытое окно агента и его браузер. Не удаляйте `agent.lock`, пока процесс действительно работает. Зависшая после аварии блокировка распознаётся Python-лаунчером по PID.

## Самопроверка

Автономный пакет проверяется после распаковки вне репозитория:

```text
BlueDotAgent.exe --self-test --require-frozen --browser firefox
BlueDotAgent.app/Contents/MacOS/BlueDotAgent --self-test --require-frozen --browser firefox
```

До первой загрузки Firefox ожидается `browser_status: "download_required"` при общем `ok: true`. Для Chrome нужен реальный установленный Google Chrome.

## Диагностика разработчика

`playlist-probe` выполняет ограниченный headed-запуск, а `probe-network` используется только когда нужны данные уровня запросов. Логи редактируют известные credentials и query strings, но всё равно считаются приватной диагностикой аккаунта.

```powershell
.\scripts\playlist-probe.ps1 "спокойный ненапряжный трек"
.\scripts\probe-network.ps1 -Seconds 120
.\scripts\state-probe.ps1 "спокойный ненапряжный трек" -ViaReact -IncludeAdvanced -Seconds 20
```

## Ограничения

- Поиск React-контекста зависит от внутреннего дерева Blue Dot и может потребовать обновления после изменений сайта.
- Панели нужен один настроенный ИИ-провайдер; локальные правила остаются доступны CLI-сценариям.
- Artlist и Epidemic пока не имеют рабочих адаптеров.
- Blue Dot не предоставляет отдельный фильтр тембральной окраски; такие различия требуют прослушивания.
