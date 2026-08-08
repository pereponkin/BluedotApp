from __future__ import annotations

from typing import Any


HELP_LINKS = {
    "gemini_key": "https://aistudio.google.com/app/apikey",
    "gemini_limits": "https://aistudio.google.com/rate-limit",
    "groq_key": "https://console.groq.com/keys",
    "groq_limits": "https://console.groq.com/docs/rate-limits",
    "openrouter_key": "https://openrouter.ai/settings/keys",
    "openrouter_limits": "https://openrouter.ai/docs/faq",
    "mistral_key": "https://console.mistral.ai/api-keys/",
    "mistral_limits": "https://admin.mistral.ai/plateforme/limits",
}

HELP_TITLE = "Blue Dot Agent"
HELP_SUBTITLE = "Справка по ИИ-сервисам, настройке и поиску музыки"

HELP_TABS: tuple[dict[str, Any], ...] = (
    {
        "title": "О проекте",
        "blocks": (
            {"kind": "title", "text": "Что делает помощник"},
            {
                "kind": "body",
                "text": (
                    "Blue Dot Agent — локальный ИИ-помощник для каталога Blue Dot Sessions. "
                    "Он понимает смысл свободного человеческого запроса, переводит его в шкалы "
                    "и категории Blue Dot и запускает один точный поиск на открытой странице."
                ),
            },
            {"kind": "heading", "text": "Что остаётся под вашим контролем"},
            {
                "kind": "body",
                "text": (
                    "Помощник не запускает воспроизведение автоматически. Вы сами слушаете треки, "
                    "выбираете вариации и скачиваете их штатными средствами Blue Dot. При ошибке ИИ "
                    "существующие фильтры страницы не изменяются."
                ),
            },
        ),
    },
    {
        "title": "Установка",
        "blocks": (
            {"kind": "title", "text": "Регистрация и API-ключи"},
            {
                "kind": "body",
                "text": (
                    "Достаточно зарегистрироваться в одном сервисе. Остальные можно добавить позже. "
                    "Созданный ключ вставляйте только через кнопку «Ввести / заменить API-ключ» "
                    "в настройках Blue Dot Agent."
                ),
            },
            {"kind": "heading", "text": "Google AI Studio (Gemini)"},
            {
                "kind": "body",
                "text": (
                    "Войдите с учётной записью Google, примите условия AI Studio и откройте API Keys. "
                    "Для нового пользователя Google обычно создаёт проект и ключ автоматически; "
                    "иначе нажмите Create API key."
                ),
            },
            {"kind": "link", "text": "Открыть ключи Gemini", "url": HELP_LINKS["gemini_key"]},
            {"kind": "heading", "text": "Groq"},
            {
                "kind": "body",
                "text": (
                    "Зарегистрируйтесь или войдите в GroqCloud, откройте API Keys, нажмите Create API Key, "
                    "задайте понятное имя и сразу скопируйте показанный ключ."
                ),
            },
            {"kind": "link", "text": "Открыть ключи Groq", "url": HELP_LINKS["groq_key"]},
            {"kind": "heading", "text": "OpenRouter"},
            {
                "kind": "body",
                "text": (
                    "Создайте аккаунт OpenRouter, откройте Keys и нажмите Create Key. Пополнять баланс "
                    "для выбранной в помощнике модели с суффиксом :free не требуется."
                ),
            },
            {"kind": "link", "text": "Открыть ключи OpenRouter", "url": HELP_LINKS["openrouter_key"]},
            {"kind": "heading", "text": "Mistral"},
            {
                "kind": "body",
                "text": (
                    "Создайте аккаунт Mistral, оставьте режим Free, откройте API Keys и нажмите "
                    "Create new key. Для помощника нужен обычный API-ключ Studio, а не ключ Vibe Code CLI."
                ),
            },
            {"kind": "link", "text": "Открыть ключи Mistral", "url": HELP_LINKS["mistral_key"]},
        ),
    },
    {
        "title": "Использование",
        "blocks": (
            {"kind": "title", "text": "Первый поиск"},
            {"kind": "step", "text": "1. Запустите Blue Dot Agent и дождитесь открытия выбранного браузера."},
            {
                "kind": "body",
                "text": (
                    "Google Chrome используется из системы. При первом выборе Firefox помощник "
                    "предложит один раз скачать совместимую сборку Playwright (около 120 МБ)."
                ),
            },
            {"kind": "step", "text": "2. Нажмите шестерёнку в верхней части панели."},
            {"kind": "step", "text": "3. Выберите ИИ-сервис и модель."},
            {
                "kind": "step",
                "text": (
                    "4. Нажмите «Ввести / заменить API-ключ», вставьте ключ в отдельное окно "
                    "и нажмите «Применить»."
                ),
            },
            {
                "kind": "step",
                "text": "5. Опишите нужную музыку обычными словами и нажмите Enter или кнопку «Найти».",
            },
            {"kind": "heading", "text": "Примеры запросов"},
            {"kind": "quote", "text": "Динамичный напряжённый детектив"},
            {"kind": "quote", "text": "Тёплая немного неловкая романтика на пляже"},
            {"kind": "quote", "text": "Спокойные редкие струнные для серьёзного рассказа"},
            {"kind": "heading", "text": "Как читать результат"},
            {
                "kind": "body",
                "text": (
                    "Панель показывает выбранный ИИ, реально применённые шкалы и категории, число "
                    "точных совпадений и наличие похожих треков. Чипы фильтров появляются в верхней "
                    "части сайта Blue Dot; любой из них можно снять вручную."
                ),
            },
            {"kind": "heading", "text": "Возврат к прошлым запросам"},
            {
                "kind": "body",
                "text": (
                    "Каждый запрос из панели становится точкой в истории браузера. Кнопка «Назад» "
                    "возвращает предыдущую конфигурацию фильтров и её сводку, «Вперёд» — снова "
                    "показывает более поздний запрос. Возврат до самого первого запроса сбрасывает "
                    "фильтры к исходному состоянию страницы."
                ),
            },
            {"kind": "heading", "text": "Новые запросы и перезапуск"},
            {
                "kind": "body",
                "text": (
                    "Для каждого нового запроса перезапускать браузер не нужно: измените текст в поле "
                    "запроса и снова нажмите Enter или «Найти». Закройте выбранный браузер только перед тем, как "
                    "запустить Blue Dot Agent ещё раз — две копии помощника не могут одновременно "
                    "использовать один профиль."
                ),
            },
        ),
    },
    {
        "title": "ИИ и данные",
        "blocks": (
            {"kind": "title", "text": "Бесплатные модели и лимиты"},
            {
                "kind": "body",
                "text": (
                    "Помощник ориентирован только на модели, доступные без оплаты в бесплатных режимах "
                    "сервисов. Он сам не подключает биллинг и не переводит аккаунт на платный тариф. "
                    "Если вы включили оплату вручную, начинают действовать условия вашего аккаунта."
                ),
            },
            {"kind": "heading", "text": "Google AI Studio (Gemini)"},
            {
                "kind": "body",
                "text": (
                    "Gemini 3.5 Flash-Lite и Gemini 3.5 Flash доступны в Free tier. Единого обещанного "
                    "числа запросов в сутки сейчас нет: фактический RPD задаётся для проекта и модели "
                    "и отображается в AI Studio. Суточная квота сбрасывается в полночь "
                    "по тихоокеанскому времени."
                ),
            },
            {
                "kind": "link",
                "text": "Посмотреть текущий лимит Gemini",
                "url": HELP_LINKS["gemini_limits"],
            },
            {"kind": "heading", "text": "Groq"},
            {
                "kind": "body",
                "text": (
                    "openai/gpt-oss-120b и openai/gpt-oss-20b на Free plan: до 1000 запросов в сутки "
                    "на модель. Дополнительно действуют 30 запросов в минуту и токенные ограничения."
                ),
            },
            {"kind": "link", "text": "Открыть таблицу лимитов Groq", "url": HELP_LINKS["groq_limits"]},
            {"kind": "heading", "text": "OpenRouter"},
            {
                "kind": "body",
                "text": (
                    "openai/gpt-oss-20b:free: 50 бесплатных запросов в сутки суммарно по всем "
                    "free-моделям. Лимит 1000 в сутки появляется только после покупки минимум $10 "
                    "кредитов и поэтому не относится к полностью бесплатному режиму."
                ),
            },
            {
                "kind": "link",
                "text": "Открыть правила Free tier OpenRouter",
                "url": HELP_LINKS["openrouter_limits"],
            },
            {"kind": "heading", "text": "Mistral"},
            {
                "kind": "body",
                "text": (
                    "mistral-small-latest и ministral-8b-latest доступны в режиме Free для тестирования. "
                    "Отдельный публичный лимит запросов в сутки не установлен: Mistral ограничивает "
                    "запросы в секунду, токены в минуту и токены в месяц. Точные значения показаны "
                    "на странице Limits вашей организации."
                ),
            },
            {
                "kind": "link",
                "text": "Посмотреть текущие лимиты Mistral",
                "url": HELP_LINKS["mistral_limits"],
            },
            {"kind": "heading", "text": "Переключение"},
            {
                "kind": "body",
                "text": (
                    "Для каждого сервиса ключ сохраняется отдельно. При переключении на другой "
                    "сервис ранее сохранённый ключ не удаляется, поэтому вводить его заново не нужно."
                ),
            },
            {"kind": "heading", "text": "Где хранятся данные"},
            {
                "kind": "body",
                "text": (
                    "На Windows настройки находятся в %LOCALAPPDATA%\\BlueDotAgent, на macOS — "
                    "в ~/Library/Application Support/BlueDotAgent. API-ключи защищены Windows DPAPI "
                    "или системным Keychain macOS и не передаются JavaScript-коду страницы Blue Dot."
                ),
            },
            {
                "kind": "body",
                "text": (
                    "Firefox и Chrome используют отдельные профили внутри папки данных агента. "
                    "Диагностика хранится в папке logs, а скачанные треки — в папке, указанной "
                    "под шестерёнкой. По умолчанию используется системная папка «Загрузки»."
                ),
            },
            {"kind": "heading", "text": "Если поиск не сработал"},
            {
                "kind": "body",
                "text": (
                    "Проверьте выбранную модель, API-ключ, доступность сервиса и подключение к интернету. "
                    "После исправления повторите тот же запрос — при ошибке старые фильтры не меняются."
                ),
            },
        ),
    },
)

HELP_BLOCK_KINDS = frozenset({"title", "heading", "body", "step", "quote", "link"})


def help_document() -> dict[str, Any]:
    """Return the help content as plain JSON-serializable data."""

    return {
        "title": HELP_TITLE,
        "subtitle": HELP_SUBTITLE,
        "tabs": [
            {"title": tab["title"], "blocks": [dict(block) for block in tab["blocks"]]}
            for tab in HELP_TABS
        ],
    }
