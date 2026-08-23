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

EN_HELP_SUBTITLE = "AI services, setup, and music search guide"

EN_HELP_TABS: tuple[dict[str, Any], ...] = (
    {
        "title": "About",
        "blocks": (
            {"kind": "title", "text": "What the assistant does"},
            {
                "kind": "body",
                "text": (
                    "Blue Dot Agent is a local AI assistant for the Blue Dot Sessions catalog. "
                    "It understands a natural-language request, translates its meaning into Blue Dot "
                    "scales and categories, and runs one precise search on the open page."
                ),
            },
            {"kind": "heading", "text": "What stays under your control"},
            {
                "kind": "body",
                "text": (
                    "The assistant never starts playback automatically. You listen to tracks, choose "
                    "variations, and download them using Blue Dot's normal controls. Existing page "
                    "filters remain unchanged if the AI request fails."
                ),
            },
        ),
    },
    {
        "title": "Setup",
        "blocks": (
            {"kind": "title", "text": "Registration and API keys"},
            {
                "kind": "body",
                "text": (
                    "You only need to register with one service; others can be added later. Enter a "
                    "new key only through the “Enter / replace API key” button in Blue Dot Agent settings."
                ),
            },
            {"kind": "heading", "text": "Google AI Studio (Gemini)"},
            {
                "kind": "body",
                "text": (
                    "Sign in with a Google account, accept the AI Studio terms, and open API Keys. "
                    "Google usually creates a project and key for a new user automatically; otherwise "
                    "select Create API key."
                ),
            },
            {"kind": "link", "text": "Open Gemini keys", "url": HELP_LINKS["gemini_key"]},
            {"kind": "heading", "text": "Groq"},
            {
                "kind": "body",
                "text": (
                    "Register or sign in to GroqCloud, open API Keys, select Create API Key, give it a "
                    "recognizable name, and copy the displayed key immediately."
                ),
            },
            {"kind": "link", "text": "Open Groq keys", "url": HELP_LINKS["groq_key"]},
            {"kind": "heading", "text": "OpenRouter"},
            {
                "kind": "body",
                "text": (
                    "Create an OpenRouter account, open Keys, and select Create Key. The model selected "
                    "in the assistant has the :free suffix and does not require account credit."
                ),
            },
            {"kind": "link", "text": "Open OpenRouter keys", "url": HELP_LINKS["openrouter_key"]},
            {"kind": "heading", "text": "Mistral"},
            {
                "kind": "body",
                "text": (
                    "Create a Mistral account, keep the Free plan, open API Keys, and select Create new "
                    "key. Blue Dot Agent needs a regular Studio API key, not a Vibe Code CLI key."
                ),
            },
            {"kind": "link", "text": "Open Mistral keys", "url": HELP_LINKS["mistral_key"]},
        ),
    },
    {
        "title": "Using the app",
        "blocks": (
            {"kind": "title", "text": "Your first search"},
            {"kind": "step", "text": "1. Start Blue Dot Agent and wait for the selected browser to open."},
            {
                "kind": "body",
                "text": (
                    "Google Chrome is used from your system. The first time you choose Firefox, the "
                    "assistant offers to download a compatible Playwright build (about 120 MB) once."
                ),
            },
            {"kind": "step", "text": "2. Select the gear at the top of the panel."},
            {"kind": "step", "text": "3. Choose an AI service and model."},
            {
                "kind": "step",
                "text": (
                    "4. Select “Enter / replace API key”, paste the key into the separate window, "
                    "and select Apply."
                ),
            },
            {
                "kind": "step",
                "text": "5. Describe the music in ordinary language and press Enter or select Search.",
            },
            {"kind": "heading", "text": "Example requests"},
            {"kind": "quote", "text": "A dynamic, tense detective scene"},
            {"kind": "quote", "text": "Warm, slightly awkward romance on a beach"},
            {"kind": "quote", "text": "Calm sparse strings for a serious story"},
            {"kind": "heading", "text": "Reading the result"},
            {
                "kind": "body",
                "text": (
                    "The panel shows the selected AI, the scales and categories actually applied, the "
                    "exact-match count, and whether related tracks are available. Filter chips appear "
                    "at the top of Blue Dot and can still be removed manually."
                ),
            },
            {"kind": "heading", "text": "Returning to earlier searches"},
            {
                "kind": "body",
                "text": (
                    "Each panel search becomes a point in browser history. Back restores the previous "
                    "filter configuration and summary; Forward returns to a later request. Going back "
                    "before the first search restores the page's original filters."
                ),
            },
            {"kind": "heading", "text": "New searches and restarting"},
            {
                "kind": "body",
                "text": (
                    "You do not need to restart the browser for every request: edit the query and press "
                    "Enter or Search again. Close the selected browser only before starting Blue Dot "
                    "Agent again, because two copies cannot use the same profile at once."
                ),
            },
        ),
    },
    {
        "title": "AI and data",
        "blocks": (
            {"kind": "title", "text": "Free models and limits"},
            {
                "kind": "body",
                "text": (
                    "The assistant is limited to models available at no cost in provider free tiers. "
                    "It does not enable billing or move an account to a paid plan. If you enable billing "
                    "yourself, your account's own terms apply."
                ),
            },
            {"kind": "heading", "text": "Google AI Studio (Gemini)"},
            {
                "kind": "body",
                "text": (
                    "Gemini 3.5 Flash-Lite and Gemini 3.5 Flash are available in the Free tier. There is "
                    "no single guaranteed daily request count: actual RPD depends on the project and "
                    "model and is shown in AI Studio. Daily quotas reset at midnight Pacific time."
                ),
            },
            {"kind": "link", "text": "View the current Gemini limit", "url": HELP_LINKS["gemini_limits"]},
            {"kind": "heading", "text": "Groq"},
            {
                "kind": "body",
                "text": (
                    "openai/gpt-oss-120b and openai/gpt-oss-20b on the Free plan allow up to 1,000 "
                    "requests per day per model. A 30 requests-per-minute limit and token limits also apply."
                ),
            },
            {"kind": "link", "text": "Open the Groq limits table", "url": HELP_LINKS["groq_limits"]},
            {"kind": "heading", "text": "OpenRouter"},
            {
                "kind": "body",
                "text": (
                    "openai/gpt-oss-20b:free allows 50 free requests per day in total across free models. "
                    "The 1,000-per-day limit requires at least $10 in purchased credits and is therefore "
                    "not part of the completely free mode."
                ),
            },
            {"kind": "link", "text": "Open the OpenRouter Free tier rules", "url": HELP_LINKS["openrouter_limits"]},
            {"kind": "heading", "text": "Mistral"},
            {
                "kind": "body",
                "text": (
                    "mistral-small-latest and ministral-8b-latest are available in Free testing mode. "
                    "There is no separate public daily request cap; Mistral limits requests per second, "
                    "tokens per minute, and tokens per month. Exact values appear on your organization's Limits page."
                ),
            },
            {"kind": "link", "text": "View current Mistral limits", "url": HELP_LINKS["mistral_limits"]},
            {"kind": "heading", "text": "Switching services"},
            {
                "kind": "body",
                "text": (
                    "Each service has its own saved key. Switching to another service does not delete a "
                    "previously saved key, so you do not need to enter it again."
                ),
            },
            {"kind": "heading", "text": "Where data is stored"},
            {
                "kind": "body",
                "text": (
                    "On Windows, settings are stored in %LOCALAPPDATA%\\BlueDotAgent; on macOS, in "
                    "~/Library/Application Support/BlueDotAgent. API keys are protected by Windows DPAPI "
                    "or the macOS system Keychain and are never exposed to JavaScript on the Blue Dot page."
                ),
            },
            {
                "kind": "body",
                "text": (
                    "Firefox and Chrome use separate profiles inside the agent data directory. Diagnostics "
                    "are kept in logs, and downloaded tracks go to the folder selected under the gear. The "
                    "system Downloads folder is used by default."
                ),
            },
            {"kind": "heading", "text": "If a search fails"},
            {
                "kind": "body",
                "text": (
                    "Check the selected model, API key, service availability, and internet connection. "
                    "Then repeat the same request; existing filters remain unchanged after an error."
                ),
            },
        ),
    },
)

HELP_BLOCK_KINDS = frozenset({"title", "heading", "body", "step", "quote", "link"})


def help_document() -> dict[str, dict[str, Any]]:
    """Return localized help content as plain JSON-serializable data."""

    return {
        language: {
            "title": HELP_TITLE,
            "subtitle": subtitle,
            "tabs": [
                {
                    "title": tab["title"],
                    "blocks": [dict(block) for block in tab["blocks"]],
                }
                for tab in tabs
            ],
        }
        for language, subtitle, tabs in (
            ("ru", HELP_SUBTITLE, HELP_TABS),
            ("en", EN_HELP_SUBTITLE, EN_HELP_TABS),
        )
    }
