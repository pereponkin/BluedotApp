(() => {
  if (window.top !== window || location.hostname !== "app.sessions.blue") return;
  const runId = "__BLUEDOT_PANEL_RUN_ID__";

  const mount = () => {
    if (!document.documentElement || document.getElementById("bluedot-agent-panel")) return;

    const host = document.createElement("div");
    host.id = "bluedot-agent-panel";
    Object.assign(host.style, {
      position: "fixed",
      inset: "0 auto 0 0",
      width: "340px",
      zIndex: "600"
    });
    document.documentElement.append(host);
    const shadow = host.attachShadow({ mode: "open" });
    shadow.addEventListener("keydown", (event) => event.stopPropagation());
    shadow.addEventListener("keyup", (event) => event.stopPropagation());
    shadow.innerHTML = `
      <style>
        :host {
          --color-paper: oklch(21% 0.008 260);
          --color-paper-2: oklch(25% 0.009 260);
          --color-paper-3: oklch(29% 0.012 260);
          --color-ink: oklch(96% 0.008 260);
          --color-ink-2: oklch(76% 0.012 260);
          --color-muted: oklch(64% 0.014 260);
          --color-rule: oklch(34% 0.014 260);
          --color-rule-strong: oklch(45% 0.025 260);
          --color-accent: oklch(66% 0.13 285);
          --color-accent-ink: oklch(17% 0.025 285);
          --color-focus: oklch(76% 0.13 250);
          --color-error: oklch(76% 0.13 25);
          --color-success: oklch(74% 0.11 155);
          --color-warning: oklch(82% 0.11 80);
          --font-display: "Bahnschrift", "Arial Narrow", sans-serif;
          --font-body: "Segoe UI Variable Text", "Segoe UI", sans-serif;
          --font-outlier: "Cascadia Mono", "Consolas", monospace;
          --space-3xs: 4px;
          --space-2xs: 8px;
          --space-xs: 12px;
          --space-sm: 16px;
          --space-md: 24px;
          --control-height: 44px;
          --radius-control: 3px;
          --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
          --dur-short: 160ms;
          --z-panel: 600;
          color-scheme: dark;
          color: var(--color-ink);
          font-family: var(--font-body);
        }
        *, *::before, *::after { box-sizing: border-box; }
        aside {
          width: 100%;
          height: 100%;
          overflow-y: auto;
          overflow-x: clip;
          color: var(--color-ink);
          background: var(--color-paper);
          border-right: 1px solid var(--color-rule);
          font: 14px/1.45 var(--font-body);
          scrollbar-color: var(--color-rule-strong) var(--color-paper);
        }
        header {
          min-height: 44px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-2xs) var(--space-xs);
          border-bottom: 1px solid var(--color-rule);
        }
        header div { display: flex; align-items: center; gap: var(--space-2xs); }
        .language-control { position: relative; display: block; }
        [data-role="language-menu"] {
          position: absolute;
          inset: calc(100% + var(--space-3xs)) 0 auto auto;
          z-index: 2;
          display: grid;
          gap: var(--space-3xs);
          min-width: 76px;
          padding: var(--space-3xs);
          background: var(--color-paper);
          border: 1px solid var(--color-rule-strong);
          box-shadow: 0 12px 28px oklch(8% 0.02 260 / .45);
        }
        [data-role="language-menu"] button {
          min-width: 0;
          min-height: 34px;
          padding-inline: var(--space-2xs);
        }
        [data-role="language-menu"] button[aria-checked="true"] {
          color: var(--color-ink);
          border-color: var(--color-accent);
          background: var(--color-paper-3);
        }
        h1 {
          margin: 0;
          min-width: 0;
          overflow-wrap: anywhere;
          color: var(--color-ink);
          font-family: var(--font-display);
          font-size: 15px;
          font-style: normal;
          font-weight: 600;
          letter-spacing: .01em;
          white-space: nowrap;
        }
        button {
          min-width: var(--control-height);
          min-height: var(--control-height);
          padding: 0 var(--space-xs);
          color: var(--color-ink);
          background: var(--color-paper-2);
          border: 1px solid var(--color-rule-strong);
          border-radius: var(--radius-control);
          cursor: pointer;
          font: 600 14px/1 var(--font-body);
          white-space: nowrap;
          transition:
            background-color var(--dur-short) var(--ease-out),
            border-color var(--dur-short) var(--ease-out),
            color var(--dur-short) var(--ease-out),
            transform 100ms var(--ease-out);
        }
        button:hover {
          color: var(--color-ink);
          background: var(--color-paper-3);
          border-color: var(--color-accent);
        }
        button:focus-visible,
        input:focus-visible,
        textarea:focus-visible,
        select:focus-visible {
          outline: 2px solid var(--color-focus);
          outline-offset: 2px;
        }
        button:active { transform: translateY(1px); }
        button:disabled,
        input:disabled,
        textarea:disabled,
        select:disabled {
          cursor: not-allowed;
          opacity: .55;
        }
        button[data-state="loading"] { cursor: wait; color: var(--color-ink-2); }
        button[data-state="error"] { border-color: var(--color-error); }
        button[data-state="success"] { border-color: var(--color-success); }
        button[data-state="confirm"] {
          color: var(--color-warning);
          border-color: var(--color-warning);
        }
        .content { padding: var(--space-xs) var(--space-xs) var(--space-md); }
        form { display: grid; gap: var(--space-2xs); }
        [data-role="settings-form"] h2 { margin-top: var(--space-xs); }
        label, h2 {
          margin: 0;
          color: var(--color-ink-2);
          font-family: var(--font-display);
          font-style: normal;
          font-weight: 600;
          letter-spacing: .06em;
          text-transform: uppercase;
        }
        label { font-size: 11px; }
        h2 { font-size: 12px; }
        input, textarea, select {
          width: 100%;
          min-height: var(--control-height);
          padding: 0 var(--space-xs);
          color: var(--color-ink);
          background: var(--color-paper-2);
          border: 1px solid var(--color-rule-strong);
          border-radius: var(--radius-control);
          outline: 2px solid transparent;
          outline-offset: 2px;
          font: 14px/1 var(--font-body);
          transition:
            background-color var(--dur-short) var(--ease-out),
            border-color var(--dur-short) var(--ease-out);
        }
        textarea[data-role="query"] {
          height: var(--control-height);
          padding-block: 11px;
          line-height: 1.45;
          overflow-wrap: anywhere;
          overflow-y: auto;
          resize: vertical;
          white-space: pre-wrap;
        }
        input[data-role="download-directory"][readonly] { cursor: pointer; }
        input:hover, textarea:hover, select:hover { border-color: var(--color-accent); }
        input:active, textarea:active, select:active { background: var(--color-paper-3); }
        input[data-state="loading"], textarea[data-state="loading"], select[data-state="loading"] { cursor: wait; }
        input[aria-invalid="true"], textarea[aria-invalid="true"], select[aria-invalid="true"] {
          border-color: var(--color-error);
        }
        input[data-state="success"], textarea[data-state="success"], select[data-state="success"] {
          border-color: var(--color-success);
        }
        input::placeholder, textarea::placeholder { color: var(--color-muted); }
        button[data-role="search"] { width: 100%; font-weight: 700; }
        [data-role="settings"] {
          margin-bottom: var(--space-sm);
          padding: var(--space-2xs) 0 var(--space-sm);
          border-bottom: 1px solid var(--color-rule);
        }
        [data-role="settings"] form { margin-top: var(--space-2xs); }
        [data-role="settings-actions"] { display: grid; gap: var(--space-2xs); }
        [data-role="key-state"] {
          min-height: 1lh;
          margin: var(--space-3xs) 0;
          color: var(--color-muted);
          font-size: 12px;
        }
        [data-role="status"] {
          min-height: 1lh;
          margin: var(--space-xs) 0;
          color: var(--color-muted);
          font-size: 12px;
        }
        [data-role="status"][data-kind="error"] { color: var(--color-error); }
        [data-role="status"][data-kind="success"] { color: var(--color-success); }
        [data-role="status"][data-kind="loading"] { color: var(--color-ink-2); }
        [data-role="warning"] {
          padding: var(--space-2xs) 0;
          color: var(--color-warning);
          border-block: 1px solid var(--color-rule);
        }
        [data-role="result"] { display: grid; gap: var(--space-xs); }
        [data-role="result"][hidden], [hidden] { display: none !important; }
        [data-role="result"] p { margin: 0; }
        [data-role="result"] section {
          display: grid;
          gap: var(--space-3xs);
          padding-top: var(--space-2xs);
          border-top: 1px solid var(--color-rule);
        }
        [data-role="result"] h2 { margin: 0; }
        [data-role="result"] div div {
          display: grid;
          grid-template-columns: minmax(5.5rem, auto) minmax(0, 1fr);
          gap: var(--space-2xs);
          padding: var(--space-3xs) 0;
          overflow-wrap: anywhere;
        }
        [data-role="result"] b {
          min-width: 0;
          color: var(--color-ink-2);
          font-family: var(--font-display);
          font-weight: 600;
        }
        [data-role="exact"] { font-family: var(--font-outlier); font-variant-numeric: tabular-nums; }
        [data-role="help"] {
          position: fixed;
          inset: 0;
          z-index: 700;
          display: grid;
          place-items: center;
          padding: var(--space-md);
          overscroll-behavior: contain;
          background: oklch(12% 0.012 260 / .64);
        }
        [data-role="help-dialog"] {
          display: grid;
          grid-template-rows: auto auto minmax(0, 1fr);
          width: min(760px, 100%);
          max-height: min(680px, 86vh);
          background: var(--color-paper);
          border: 1px solid var(--color-rule-strong);
          border-radius: var(--radius-control);
          box-shadow: 0 24px 64px oklch(8% 0.02 260 / .55);
          overflow: clip;
        }
        [data-role="help-header"] {
          display: flex;
          align-items: start;
          justify-content: space-between;
          gap: var(--space-sm);
          padding: var(--space-sm) var(--space-md);
          border-bottom: 1px solid var(--color-rule);
        }
        [data-role="help-header"] h2 {
          color: var(--color-ink);
          font-size: 18px;
          letter-spacing: .01em;
          text-transform: none;
        }
        [data-role="help-header"] p {
          margin: var(--space-3xs) 0 0;
          color: var(--color-muted);
          font-size: 12px;
        }
        [data-role="help-tabs"] {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-3xs);
          padding: var(--space-2xs) var(--space-md) 0;
          border-bottom: 1px solid var(--color-rule);
        }
        [data-role="help-tabs"] button {
          min-width: 0;
          min-height: 36px;
          padding: 0 var(--space-2xs);
          color: var(--color-muted);
          background: transparent;
          border: 1px solid transparent;
          border-bottom: 2px solid transparent;
          border-radius: 0;
          font-size: 13px;
        }
        [data-role="help-tabs"] button:hover {
          color: var(--color-ink);
          background: var(--color-paper-2);
          border-color: transparent;
        }
        [data-role="help-tabs"] button[aria-selected="true"] {
          color: var(--color-ink);
          border-bottom-color: var(--color-accent);
        }
        [data-role="help-body"] {
          padding: var(--space-sm) var(--space-md) var(--space-md);
          overflow-y: auto;
          overscroll-behavior: contain;
          scrollbar-color: var(--color-rule-strong) var(--color-paper);
        }
        [data-role="help-body"] [role="tabpanel"]:focus-visible {
          outline: 2px solid var(--color-focus);
          outline-offset: -2px;
        }
        .help-title {
          margin: 0 0 var(--space-xs);
          color: var(--color-ink);
          font-family: var(--font-display);
          font-size: 17px;
          font-weight: 600;
        }
        .help-heading {
          margin: var(--space-sm) 0 var(--space-3xs);
          color: var(--color-ink-2);
          font-family: var(--font-display);
          font-size: 12px;
          font-weight: 600;
          letter-spacing: .06em;
          text-transform: uppercase;
        }
        .help-body { margin: 0 0 var(--space-2xs); color: var(--color-ink); }
        .help-step { margin: 0 0 var(--space-3xs); padding-left: var(--space-xs); color: var(--color-ink); }
        .help-quote {
          margin: 0 0 var(--space-3xs);
          padding-left: var(--space-sm);
          color: oklch(85% 0.06 285);
          font-style: italic;
        }
        .help-link {
          display: inline-block;
          margin: 0 0 var(--space-2xs);
          color: var(--color-focus);
        }
        .help-link:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
        @media (max-width: 639px) {
          [data-role="help"] { padding: var(--space-2xs); }
          [data-role="help-dialog"] { max-height: 92vh; }
          [data-role="help-header"], [data-role="help-body"] { padding-inline: var(--space-sm); }
          [data-role="help-tabs"] { padding-inline: var(--space-sm); }
        }
        :host([data-overlay]) { box-shadow: 1px 0 0 var(--color-rule); }
        :host([data-collapsed]) h1,
        :host([data-collapsed]) [data-role="help-toggle"],
        :host([data-collapsed]) .language-control,
        :host([data-collapsed]) [data-role="settings-toggle"],
        :host([data-collapsed]) .content { display: none; }
        :host([data-collapsed]) header { justify-content: center; padding-inline: 0; }
        @media (max-width: 399px) {
          .content { padding-inline: var(--space-2xs); }
          [data-role="result"] div div { grid-template-columns: 1fr; gap: 0; }
        }
        @media (prefers-reduced-motion: reduce) {
          button, input, textarea, select { transition-duration: 0ms; }
          button:active { transform: none; }
        }
      </style>
      <aside aria-label="Blue Dot Agent">
        <header>
          <h1>Blue Dot Agent</h1>
          <div>
            <button
              data-role="help-toggle"
              type="button"
              aria-label="Справка о Blue Dot Agent"
              aria-haspopup="dialog"
              aria-expanded="false"
            >?</button>
            <span class="language-control">
              <button
                data-role="language-toggle"
                type="button"
                aria-label="Язык интерфейса"
                aria-haspopup="menu"
                aria-expanded="false"
              >🌐</button>
              <span data-role="language-menu" role="menu" aria-label="Язык интерфейса" hidden>
                <button type="button" role="menuitemradio" data-language="ru" aria-checked="true">RU</button>
                <button type="button" role="menuitemradio" data-language="en" aria-checked="false">EN</button>
              </span>
            </span>
            <button
              data-role="settings-toggle"
              type="button"
              aria-label="Настройки"
              aria-controls="bluedot-agent-settings"
              aria-expanded="false"
            >⚙</button>
            <button data-role="toggle" type="button" aria-label="Свернуть панель" aria-expanded="true">‹</button>
          </div>
        </header>
        <section class="content">
          <section id="bluedot-agent-settings" data-role="settings" hidden>
            <form data-role="settings-form">
              <label for="bluedot-agent-download-directory">Папка для скачивания:</label>
              <input
                id="bluedot-agent-download-directory"
                data-role="download-directory"
                type="text"
                autocomplete="off"
                spellcheck="false"
                readonly
                aria-haspopup="dialog"
                title="Выбрать папку"
                placeholder="Полный путь к папке"
              >
              <label for="bluedot-agent-browser">Браузер</label>
              <select id="bluedot-agent-browser" data-role="browser">
                <option value="firefox">Firefox</option>
                <option value="chrome">Google Chrome</option>
              </select>
              <p data-role="browser-note">Изменение действует после следующего запуска.</p>
              <h2>Настройки ИИ</h2>
              <label for="bluedot-agent-provider">Сервис</label>
              <select id="bluedot-agent-provider" data-role="provider"></select>
              <label for="bluedot-agent-model">Модель</label>
              <select id="bluedot-agent-model" data-role="model"></select>
              <p data-role="key-state">Ключ не сохранён.</p>
              <div data-role="settings-actions">
                <button data-role="save-settings" type="submit">Применить</button>
                <button data-role="set-api-key" type="button">Ввести / заменить API-ключ</button>
                <button data-role="clear-api-key" type="button">Удалить ключ</button>
              </div>
            </form>
          </section>
          <form data-role="search-form">
            <label for="bluedot-agent-query">Запрос</label>
            <textarea
              id="bluedot-agent-query"
              data-role="query"
              rows="1"
              maxlength="1000"
              autocomplete="off"
              placeholder="Например: спокойные струнные…"
            ></textarea>
            <button data-role="search" type="submit">Найти</button>
          </form>
          <p data-role="status" data-kind="idle" role="status" aria-live="polite">Введите запрос и нажмите Enter.</p>
          <section data-role="result" hidden>
            <p data-role="interpretation"></p>
            <p data-role="warning" hidden></p>
            <section data-role="sliders-section" hidden>
              <h2>Шкалы</h2>
              <div data-role="sliders"></div>
            </section>
            <section data-role="categories-section" hidden>
              <h2>Категории</h2>
              <div data-role="categories"></div>
            </section>
            <section data-role="missing-section" hidden>
              <h2>Не применились</h2>
              <div data-role="missing"></div>
            </section>
            <p data-role="exact"></p>
            <p data-role="related"></p>
          </section>
        </section>
      </aside>
      <div data-role="help" hidden>
        <section
          data-role="help-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="bluedot-agent-help-title"
          tabindex="-1"
        >
          <div data-role="help-header">
            <div>
              <h2 id="bluedot-agent-help-title" data-role="help-title"></h2>
              <p data-role="help-subtitle"></p>
            </div>
            <button data-role="help-close" type="button" aria-label="Закрыть справку">✕</button>
          </div>
          <div data-role="help-tabs" role="tablist" aria-label="Разделы справки"></div>
          <div data-role="help-body"></div>
        </section>
      </div>
    `;

    const panelBody = shadow.querySelector("aside");
    const toggle = shadow.querySelector("[data-role=toggle]");
    const helpToggle = shadow.querySelector("[data-role=help-toggle]");
    const languageToggle = shadow.querySelector("[data-role=language-toggle]");
    const languageMenu = shadow.querySelector("[data-role=language-menu]");
    const languageOptions = [...languageMenu.querySelectorAll("[data-language]")];
    const settingsToggle = shadow.querySelector("[data-role=settings-toggle]");
    const settingsSection = shadow.querySelector("[data-role=settings]");
    const settingsForm = shadow.querySelector("[data-role=settings-form]");
    const providerSelect = shadow.querySelector("[data-role=provider]");
    const modelSelect = shadow.querySelector("[data-role=model]");
    const browserSelect = shadow.querySelector("[data-role=browser]");
    const downloadDirectory = shadow.querySelector("[data-role=download-directory]");
    const keyState = shadow.querySelector("[data-role=key-state]");
    const saveSettings = shadow.querySelector("[data-role=save-settings]");
    const setApiKey = shadow.querySelector("[data-role=set-api-key]");
    const clearApiKey = shadow.querySelector("[data-role=clear-api-key]");
    const form = shadow.querySelector("[data-role=search-form]");
    const query = shadow.querySelector("[data-role=query]");
    const search = shadow.querySelector("[data-role=search]");
    const status = shadow.querySelector("[data-role=status]");
    const resultSection = shadow.querySelector("[data-role=result]");
    const interpretation = shadow.querySelector("[data-role=interpretation]");
    const warning = shadow.querySelector("[data-role=warning]");
    const sliders = shadow.querySelector("[data-role=sliders]");
    const categories = shadow.querySelector("[data-role=categories]");
    const missing = shadow.querySelector("[data-role=missing]");
    const helpOverlay = shadow.querySelector("[data-role=help]");
    const helpDialog = shadow.querySelector("[data-role=help-dialog]");
    const helpClose = shadow.querySelector("[data-role=help-close]");
    const helpTabs = shadow.querySelector("[data-role=help-tabs]");
    const helpBody = shadow.querySelector("[data-role=help-body]");
    const helpDocuments = __BLUEDOT_HELP_CONTENT__;
    const helpPanels = [];
    const translations = {
      ru: {
        help_label: "Справка о Blue Dot Agent",
        language_label: "Язык интерфейса",
        settings_label: "Настройки",
        collapse: "Свернуть панель",
        expand: "Развернуть панель",
        download_folder: "Папка для скачивания:",
        choose_folder: "Выбрать папку",
        path_placeholder: "Полный путь к папке",
        browser: "Браузер",
        browser_note: "Изменение действует после следующего запуска.",
        ai_settings: "Настройки ИИ",
        service: "Сервис",
        model: "Модель",
        key_saved: "Ключ сохранён или задан через переменную окружения.",
        key_missing: "Ключ не сохранён.",
        apply: "Применить",
        set_key: "Ввести / заменить API-ключ",
        delete_key: "Удалить ключ",
        delete_confirm: "Нажмите ещё раз для удаления",
        query: "Запрос",
        query_placeholder: "Например: спокойные струнные…",
        search: "Найти",
        searching: "Ищу…",
        initial_status: "Введите запрос и нажмите Enter.",
        scales: "Шкалы",
        categories: "Категории",
        missing: "Не применились",
        close_help: "Закрыть справку",
        help_sections: "Разделы справки",
        local_rules: "Локальные правила",
        last_interpretation: "Последняя интерпретация: {parser}",
        exact_matches: "Точных совпадений: {count}",
        no_exact_related: "Точных совпадений нет; ниже похожие треки.",
        related: "Ниже также доступны похожие треки.",
        no_exact: "Точных совпадений нет.",
        no_related: "Похожих треков нет.",
        settings_load_failure: "Не удалось загрузить настройки. Закройте браузер агента и запустите его заново.",
        search_failure: "Не удалось выполнить поиск. Проверьте ИИ-сервис и ключ под шестерёнкой.",
        restore_failure: "Не удалось вернуть прошлый запрос. Повторите его в поле выше.",
        open_download: "Открыть скачанный файл",
        open_failure: "Не удалось открыть файл.",
        choose_provider: "Выберите ИИ-сервис и укажите API-ключ.",
        folder_failure: "Не удалось выбрать папку.",
        folder_selected: "Папка выбрана. Нажмите «Применить», чтобы сохранить её.",
        settings_failure: "Не удалось сохранить настройки.",
        settings_saved: "Настройки применены. Браузер изменится при следующем запуске.",
        settings_need_key: "Настройки применены. Для поиска ещё нужен API-ключ.",
        key_prompt: "Введите ключ в отдельном окне Blue Dot Agent.",
        key_failure: "Не удалось сохранить API-ключ.",
        key_protected: "API-ключ защищён и сохранён.",
        key_delete_warning: "Ключ будет удалён вторым нажатием. Отменить можно любым другим действием.",
        key_delete_failure: "Не удалось удалить API-ключ.",
        key_deleted: "Сохранённый API-ключ удалён.",
        prompt_required: "Введите текстовый запрос.",
        ready: "Готово.",
        restoring_baseline: "Возвращаю исходные фильтры…",
        restoring_history: "Возвращаю прошлый запрос…",
        history_shown: "Показан прошлый запрос.",
        filters_reset: "Фильтры сброшены к исходным.",
        language_failure: "Не удалось сохранить язык интерфейса.",
        generic_error: "Не удалось выполнить операцию."
      },
      en: {
        help_label: "Blue Dot Agent help",
        language_label: "Interface language",
        settings_label: "Settings",
        collapse: "Collapse panel",
        expand: "Expand panel",
        download_folder: "Download folder:",
        choose_folder: "Choose folder",
        path_placeholder: "Full folder path",
        browser: "Browser",
        browser_note: "The change takes effect after the next launch.",
        ai_settings: "AI settings",
        service: "Service",
        model: "Model",
        key_saved: "The key is saved or supplied through an environment variable.",
        key_missing: "No key is saved.",
        apply: "Apply",
        set_key: "Enter / replace API key",
        delete_key: "Delete key",
        delete_confirm: "Select again to delete",
        query: "Request",
        query_placeholder: "For example: calm sparse strings…",
        search: "Search",
        searching: "Searching…",
        initial_status: "Enter a request and press Enter.",
        scales: "Scales",
        categories: "Categories",
        missing: "Not applied",
        close_help: "Close help",
        help_sections: "Help sections",
        local_rules: "Local rules",
        last_interpretation: "Last interpretation: {parser}",
        exact_matches: "Exact matches: {count}",
        no_exact_related: "No exact matches; related tracks are shown below.",
        related: "Related tracks are also available below.",
        no_exact: "No exact matches.",
        no_related: "No related tracks.",
        settings_load_failure: "Could not load settings. Close the agent browser and start it again.",
        search_failure: "Could not run the search. Check the AI service and key under the gear.",
        restore_failure: "Could not restore the earlier request. Repeat it in the field above.",
        open_download: "Open downloaded file",
        open_failure: "Could not open the file.",
        choose_provider: "Choose an AI service and enter an API key.",
        folder_failure: "Could not choose a folder.",
        folder_selected: "Folder selected. Select Apply to save it.",
        settings_failure: "Could not save settings.",
        settings_saved: "Settings applied. The browser will change after the next launch.",
        settings_need_key: "Settings applied. An API key is still required for search.",
        key_prompt: "Enter the key in the separate Blue Dot Agent window.",
        key_failure: "Could not save the API key.",
        key_protected: "The API key is protected and saved.",
        key_delete_warning: "The key will be deleted on the second selection. Any other action cancels this.",
        key_delete_failure: "Could not delete the API key.",
        key_deleted: "The saved API key was deleted.",
        prompt_required: "Enter a text request.",
        ready: "Done.",
        restoring_baseline: "Restoring the original filters…",
        restoring_history: "Restoring the earlier request…",
        history_shown: "The earlier request is shown.",
        filters_reset: "Filters were reset to their original state.",
        language_failure: "Could not save the interface language.",
        generic_error: "The operation could not be completed."
      }
    };
    let language = "ru";
    const t = (key, values = {}) => Object.entries(values).reduce(
      (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
      translations[language][key] || translations.ru[key] || key
    );
    const pageRoot = document.getElementById("root") || document.body;
    const storagePrefix = "__bluedotAgentPanelState:";
    const storageKey = `${storagePrefix}${runId}`;
    for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = sessionStorage.key(index);
      if (key && key.startsWith(storagePrefix) && key !== storageKey) {
        sessionStorage.removeItem(key);
      }
    }
    let panelState = { query: "", result: null, collapsed: false };
    let settingsState = null;
    try {
      panelState = { ...panelState, ...JSON.parse(sessionStorage.getItem(storageKey) || "{}") };
    } catch (error) {
      panelState = { query: "", result: null, collapsed: false };
    }
    const saveState = () => {
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(panelState));
      } catch (error) {
        // Session-only state is optional when storage is unavailable.
      }
    };
    const historyKey = "bluedotAgentEntry";
    const baselineEntry = -1;
    const currentHistoryEntry = () => {
      const state = history.state;
      if (!state || typeof state !== "object") return null;
      const value = state[historyKey];
      return typeof value === "number" ? value : null;
    };
    const historyState = (index) => {
      const state = history.state && typeof history.state === "object" ? history.state : {};
      return { ...state, [historyKey]: index };
    };
    const markHistoryBaseline = () => {
      if (currentHistoryEntry() !== null) return;
      history.replaceState(historyState(baselineEntry), "", location.href);
    };
    const pushHistoryEntry = (index) => {
      history.pushState(historyState(index), "", location.href);
    };
    const renderRows = (container, values, formatValue) => {
      container.replaceChildren();
      for (const [name, value] of Object.entries(values || {})) {
        const row = document.createElement("div");
        const label = document.createElement("b");
        const text = document.createElement("span");
        label.textContent = `${name}: `;
        text.textContent = formatValue(value);
        row.append(label, text);
        container.append(row);
      }
    };
    const formatRange = (value) => `${value[0]}–${value[1]}`;
    const formatValues = (value) => value.join(", ");
    // A heading with nothing under it reads as lost data, so an empty section
    // is hidden whole.
    const renderSection = (container, values, formatValue) => {
      renderRows(container, values, formatValue);
      container.closest("section").hidden = Object.keys(values || {}).length === 0;
    };
    const setSearchState = (kind) => {
      search.dataset.state = kind;
      search.textContent = kind === "loading" ? t("searching") : t("search");
    };
    const resizeQueryToContent = ({ shrink = false } = {}) => {
      if (host.hasAttribute("data-collapsed") || !query.getClientRects().length) return;
      const queryRect = query.getBoundingClientRect();
      const currentHeight = queryRect.height || 44;
      const searchHeight = search.getBoundingClientRect().height || 44;
      const formGap = Number.parseFloat(getComputedStyle(form).rowGap) || 0;
      const maxHeight = Math.max(
        44,
        Math.floor(window.innerHeight - queryRect.top - searchHeight - formGap - 8)
      );
      query.style.maxHeight = `${maxHeight}px`;
      query.style.height = "auto";
      const contentHeight = Math.min(query.scrollHeight, maxHeight);
      query.style.height = `${Math.min(
        maxHeight,
        shrink ? contentHeight : Math.max(currentHeight, contentHeight)
      )}px`;
    };
    let queryResizeScheduled = false;
    let shrinkNextQueryResize = false;
    const scheduleQueryResize = ({ shrink = false } = {}) => {
      shrinkNextQueryResize ||= shrink;
      if (queryResizeScheduled) return;
      queryResizeScheduled = true;
      requestAnimationFrame(() => {
        const shouldShrink = shrinkNextQueryResize;
        queryResizeScheduled = false;
        shrinkNextQueryResize = false;
        resizeQueryToContent({ shrink: shouldShrink });
      });
    };
    const setLoading = (loading) => {
      form.setAttribute("aria-busy", String(loading));
      query.disabled = loading;
      search.disabled = loading;
      if (loading) {
        query.dataset.state = "loading";
        setSearchState("loading");
      } else if (search.dataset.state === "success") {
        query.dataset.state = "success";
      } else {
        query.dataset.state = "idle";
      }
    };
    let statusState = { key: "initial_status", values: {}, text: "", kind: "idle" };
    const localizedBackendText = (text) => {
      if (language === "ru" || !/[А-Яа-яЁё]/.test(text)) return text;
      const exact = {
        "Не удалось открыть скачанный файл.": "Could not open the downloaded file.",
        "Скачанный файл больше недоступен.": "The downloaded file is no longer available.",
        "API-ключ не может быть пустым.": "The API key cannot be empty.",
        "Ввод API-ключа отменён.": "API key entry was cancelled.",
        "Поиск уже выполняется.": "A search is already running."
      };
      if (exact[text]) return exact[text];
      let match = text.match(/^Скачивание началось: (.+)$/);
      if (match) return `Download started: ${match[1]}`;
      match = text.match(/^Скачано: (.+)$/);
      if (match) return `Downloaded: ${match[1]}`;
      match = text.match(/^Не удалось скачать (.+)$/);
      if (match) return `Could not download ${match[1]}`;
      match = text.match(/^(.+) не смог интерпретировать запрос\./);
      if (match) return `${match[1]} could not interpret the request. Check the API key, model, and connection.`;
      return t("generic_error");
    };
    const renderStatus = () => {
      status.textContent = statusState.key
        ? t(statusState.key, statusState.values)
        : localizedBackendText(statusState.text);
      status.dataset.kind = statusState.kind;
    };
    const setStatus = (text, kind) => {
      statusState = { key: null, values: {}, text, kind };
      renderStatus();
      status.dataset.kind = kind;
      status.removeAttribute("data-can-open");
      status.tabIndex = -1;
      status.title = "";
    };
    const setLocalizedStatus = (key, kind, values = {}) => {
      statusState = { key, values, text: "", kind };
      renderStatus();
      status.removeAttribute("data-can-open");
      status.tabIndex = -1;
      status.title = "";
    };
    const setResponseError = (response, fallbackKey) => {
      if (response && response.error) setStatus(response.error, "error");
      else setLocalizedStatus(fallbackKey, "error");
    };
    const armClearApiKey = () => {
      clearApiKey.dataset.state = "confirm";
      clearApiKey.textContent = t("delete_confirm");
      setLocalizedStatus("key_delete_warning", "idle");
    };
    const resetClearApiKey = () => {
      if (clearApiKey.dataset.state === "confirm") clearApiKey.dataset.state = "idle";
      clearApiKey.textContent = t("delete_key");
    };
    window.addEventListener("bluedot-agent-download-status", (event) => {
      const detail = event.detail || {};
      if (typeof detail.text !== "string" || !detail.text) return;
      setStatus(detail.text, detail.kind || "idle");
      status.toggleAttribute("data-can-open", detail.can_open === true);
      status.tabIndex = detail.can_open === true ? 0 : -1;
      status.title = detail.can_open === true ? t("open_download") : "";
    });
    const openDownloadedFile = async () => {
      if (!status.hasAttribute("data-can-open")) return;
      try {
        const response = await window.__bluedotPanelCommand({ type: "open_download" });
        if (!response || !response.ok) {
          setResponseError(response, "open_failure");
        }
      } catch (error) {
        setLocalizedStatus("open_failure", "error");
      }
    };
    status.addEventListener("click", openDownloadedFile);
    status.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openDownloadedFile();
    });
    const renderModels = (provider) => {
      modelSelect.replaceChildren();
      const models = [...((provider && provider.recommended_models) || [])];
      if (provider && provider.model && !models.includes(provider.model)) {
        models.unshift(provider.model);
      }
      for (const model of models) {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = model;
        modelSelect.append(option);
      }
      modelSelect.value = provider ? provider.model : "";
    };
    const renderKeyState = () => {
      const selected = settingsState && settingsState.providers[settingsState.selected_provider];
      keyState.textContent = selected && selected.has_api_key
        ? t("key_saved")
        : t("key_missing");
      clearApiKey.disabled = !(selected && selected.has_api_key);
    };
    const renderSettings = (settings) => {
      settingsState = settings;
      providerSelect.replaceChildren();
      for (const provider of Object.values(settings.providers || {})) {
        const option = document.createElement("option");
        option.value = provider.id;
        option.textContent = provider.label;
        providerSelect.append(option);
      }
      providerSelect.value = settings.selected_provider;
      browserSelect.value = settings.browser || "firefox";
      downloadDirectory.value = settings.download_directory || "";
      const selected = settings.providers[settings.selected_provider];
      renderModels(selected);
      renderKeyState();
      resetClearApiKey();
    };
    const loadSettings = async () => {
      try {
        const response = await window.__bluedotPanelCommand({ type: "get_settings" });
        if (!response || !response.ok) {
          setResponseError(response, "settings_load_failure");
          return;
        }
        language = response.settings.language === "en" ? "en" : "ru";
        renderSettings(response.settings);
        applyLanguage();
        const selected = response.settings.providers[response.settings.selected_provider];
        if (!selected || !selected.has_api_key) {
          settingsSection.hidden = false;
          settingsToggle.setAttribute("aria-expanded", "true");
          setLocalizedStatus("choose_provider", "idle");
        }
        if (panelState.result && panelState.result.ok) showResult(panelState.result);
      } catch (error) {
        setLocalizedStatus("settings_load_failure", "error");
      } finally {
        scheduleQueryResize();
      }
    };
    const showResult = (result) => {
      const configuredProvider = settingsState && settingsState.providers[result.parser];
      const parser = configuredProvider
        ? configuredProvider.label
        : result.parser === "gemini"
          ? "Gemini"
          : result.parser === "rule_based" ? t("local_rules") : result.parser;
      interpretation.textContent = t("last_interpretation", { parser });
      warning.textContent = result.warning ? localizedBackendText(result.warning) : "";
      warning.hidden = !result.warning;
      renderSection(sliders, result.applied_sliders, formatRange);
      renderSection(categories, result.categories, formatValues);
      renderSection(missing, result.missing_sliders, formatRange);
      shadow.querySelector("[data-role=exact]").textContent =
        t("exact_matches", { count: result.exact_count });
      const related = shadow.querySelector("[data-role=related]");
      if (result.exact_count === 0 && result.has_related) {
        related.textContent = t("no_exact_related");
      } else if (result.has_related) {
        related.textContent = t("related");
      } else {
        related.textContent = result.exact_count === 0
          ? t("no_exact")
          : t("no_related");
      }
      resultSection.hidden = false;
    };
    const setCollapsed = (collapsed) => {
      const overlay = window.innerWidth < 640;
      const width = collapsed ? 44 : Math.min(340, window.innerWidth);
      host.toggleAttribute("data-collapsed", collapsed);
      host.toggleAttribute("data-overlay", overlay);
      host.style.width = `${width}px`;
      document.documentElement.style.minHeight = "100%";
      document.documentElement.style.overflowX = "clip";
      document.body.style.overflowX = "clip";
      document.body.style.minWidth = "0";
      document.body.style.margin = "0";
      pageRoot.style.width = "100%";
      pageRoot.style.maxWidth = "100%";
      pageRoot.style.minHeight = "100vh";
      if (overlay) {
        document.documentElement.style.display = "";
        document.documentElement.style.gridTemplateColumns = "";
        document.body.style.gridColumn = "";
        pageRoot.style.transform = "";
      } else {
        document.documentElement.style.display = "grid";
        document.documentElement.style.gridTemplateColumns = `${width}px minmax(0, 1fr)`;
        document.body.style.gridColumn = "2";
        pageRoot.style.transform = "translateZ(0)";
      }
      toggle.setAttribute("aria-expanded", String(!collapsed));
      toggle.setAttribute("aria-label", collapsed ? t("expand") : t("collapse"));
      toggle.textContent = collapsed ? "›" : "‹";
    };
    const selectHelpTab = (index) => {
      helpPanels.forEach((item, position) => {
        const selected = position === index;
        item.button.setAttribute("aria-selected", String(selected));
        item.button.tabIndex = selected ? 0 : -1;
        item.panel.hidden = !selected;
      });
      helpBody.scrollTop = 0;
    };
    const helpBlockNode = (block) => {
      if (block.kind === "link") {
        const link = document.createElement("a");
        link.className = "help-link";
        link.href = block.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = block.text;
        const wrapper = document.createElement("p");
        wrapper.style.margin = "0";
        wrapper.append(link);
        return wrapper;
      }
      const node = document.createElement(
        block.kind === "title" ? "h3" : block.kind === "heading" ? "h4" : "p"
      );
      node.className = `help-${block.kind}`;
      node.textContent = block.text;
      return node;
    };
    const buildHelp = () => {
      helpPanels.length = 0;
      helpTabs.replaceChildren();
      helpBody.replaceChildren();
      const helpContent = helpDocuments[language] || helpDocuments.ru;
      shadow.querySelector("[data-role=help-title]").textContent = helpContent.title || "";
      shadow.querySelector("[data-role=help-subtitle]").textContent = helpContent.subtitle || "";
      (helpContent.tabs || []).forEach((tab, index) => {
        const tabId = `bluedot-agent-help-tab-${index}`;
        const panelId = `bluedot-agent-help-panel-${index}`;
        const button = document.createElement("button");
        button.type = "button";
        button.id = tabId;
        button.setAttribute("role", "tab");
        button.setAttribute("aria-controls", panelId);
        button.setAttribute("aria-selected", "false");
        button.tabIndex = -1;
        button.textContent = tab.title;
        button.addEventListener("click", () => selectHelpTab(index));
        helpTabs.append(button);
        const panel = document.createElement("div");
        panel.id = panelId;
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", tabId);
        panel.tabIndex = 0;
        panel.hidden = true;
        for (const block of tab.blocks || []) panel.append(helpBlockNode(block));
        helpBody.append(panel);
        helpPanels.push({ button, panel });
      });
      selectHelpTab(0);
    };
    const setLanguageMenuOpen = (open) => {
      languageMenu.hidden = !open;
      languageToggle.setAttribute("aria-expanded", String(open));
      if (open) languageOptions.find((option) => option.dataset.language === language)?.focus();
    };
    const applyLanguage = () => {
      host.setAttribute("lang", language);
      helpToggle.setAttribute("aria-label", t("help_label"));
      languageToggle.setAttribute("aria-label", t("language_label"));
      languageMenu.setAttribute("aria-label", t("language_label"));
      settingsToggle.setAttribute("aria-label", t("settings_label"));
      helpClose.setAttribute("aria-label", t("close_help"));
      helpTabs.setAttribute("aria-label", t("help_sections"));
      shadow.querySelector('label[for="bluedot-agent-download-directory"]').textContent = t("download_folder");
      downloadDirectory.title = t("choose_folder");
      downloadDirectory.placeholder = t("path_placeholder");
      shadow.querySelector('label[for="bluedot-agent-browser"]').textContent = t("browser");
      shadow.querySelector("[data-role=browser-note]").textContent = t("browser_note");
      shadow.querySelector("[data-role=settings-form] h2").textContent = t("ai_settings");
      shadow.querySelector('label[for="bluedot-agent-provider"]').textContent = t("service");
      shadow.querySelector('label[for="bluedot-agent-model"]').textContent = t("model");
      saveSettings.textContent = t("apply");
      setApiKey.textContent = t("set_key");
      clearApiKey.textContent = clearApiKey.dataset.state === "confirm"
        ? t("delete_confirm")
        : t("delete_key");
      shadow.querySelector('label[for="bluedot-agent-query"]').textContent = t("query");
      query.placeholder = t("query_placeholder");
      shadow.querySelector("[data-role=sliders-section] h2").textContent = t("scales");
      shadow.querySelector("[data-role=categories-section] h2").textContent = t("categories");
      shadow.querySelector("[data-role=missing-section] h2").textContent = t("missing");
      languageOptions.forEach((option) => {
        option.setAttribute("aria-checked", String(option.dataset.language === language));
      });
      setSearchState(search.dataset.state || "idle");
      renderStatus();
      if (status.hasAttribute("data-can-open")) status.title = t("open_download");
      if (settingsState) renderKeyState();
      if (panelState.result && panelState.result.ok) showResult(panelState.result);
      setCollapsed(host.hasAttribute("data-collapsed"));
      buildHelp();
    };
    const helpFocusables = () =>
      [...helpDialog.querySelectorAll('button, a[href], [tabindex="0"]')].filter(
        (node) => !node.disabled && !node.closest("[hidden]")
      );
    const setHelpOpen = (open) => {
      helpOverlay.hidden = !open;
      helpToggle.setAttribute("aria-expanded", String(open));
      // Everything outside the dialog leaves the tab order and the accessibility
      // tree, so the page behind the overlay cannot be reached or read.
      document.body.inert = open;
      panelBody.inert = open;
      if (open) {
        selectHelpTab(0);
        helpDialog.focus();
      } else {
        helpToggle.focus();
      }
    };
    toggle.addEventListener("click", () => {
      setLanguageMenuOpen(false);
      panelState.collapsed = !host.hasAttribute("data-collapsed");
      setCollapsed(panelState.collapsed);
      saveState();
      scheduleQueryResize();
    });
    languageToggle.addEventListener("click", () => setLanguageMenuOpen(languageMenu.hidden));
    languageMenu.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setLanguageMenuOpen(false);
        languageToggle.focus();
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      event.preventDefault();
      const current = languageOptions.indexOf(shadow.activeElement);
      const step = event.key === "ArrowDown" ? 1 : -1;
      languageOptions[(current + step + languageOptions.length) % languageOptions.length].focus();
    });
    languageOptions.forEach((option) => option.addEventListener("click", async () => {
      const nextLanguage = option.dataset.language;
      setLanguageMenuOpen(false);
      if (nextLanguage === language || !settingsState) return;
      const response = await window.__bluedotPanelCommand({
        type: "set_language",
        language: nextLanguage
      });
      if (!response || !response.ok) {
        setResponseError(response, "language_failure");
        return;
      }
      language = response.settings.language === "en" ? "en" : "ru";
      settingsState = response.settings;
      applyLanguage();
    }));
    shadow.addEventListener("click", (event) => {
      if (!event.composedPath().includes(languageToggle) && !event.composedPath().includes(languageMenu)) {
        setLanguageMenuOpen(false);
      }
    });
    document.addEventListener("click", (event) => {
      if (!event.composedPath().includes(host)) setLanguageMenuOpen(false);
    });
    applyLanguage();
    helpToggle.addEventListener("click", () => setHelpOpen(helpOverlay.hidden));
    helpClose.addEventListener("click", () => setHelpOpen(false));
    helpOverlay.addEventListener("click", (event) => {
      if (event.target === helpOverlay) setHelpOpen(false);
    });
    helpOverlay.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setHelpOpen(false);
        return;
      }
      if (event.key === "Tab") {
        const focusables = helpFocusables();
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = shadow.activeElement;
        if (event.shiftKey && (active === first || active === helpDialog)) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && active === last) {
          event.preventDefault();
          first.focus();
        }
        return;
      }
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const current = helpPanels.findIndex((item) => !item.panel.hidden);
      if (current < 0 || document.activeElement === null) return;
      if (!helpTabs.contains(event.composedPath()[0])) return;
      event.preventDefault();
      const step = event.key === "ArrowRight" ? 1 : -1;
      const next = (current + step + helpPanels.length) % helpPanels.length;
      selectHelpTab(next);
      helpPanels[next].button.focus();
    });
    settingsToggle.addEventListener("click", () => {
      settingsSection.hidden = !settingsSection.hidden;
      settingsToggle.setAttribute("aria-expanded", String(!settingsSection.hidden));
      resetClearApiKey();
      scheduleQueryResize();
    });
    providerSelect.addEventListener("change", () => {
      resetClearApiKey();
      if (!settingsState) return;
      const selected = settingsState.providers[providerSelect.value];
      if (!selected) return;
      renderModels(selected);
      keyState.textContent = selected.has_api_key
        ? t("key_saved")
        : t("key_missing");
      clearApiKey.disabled = !selected.has_api_key;
    });
    const chooseDownloadDirectory = async () => {
      if (downloadDirectory.dataset.state === "loading") return;
      downloadDirectory.dataset.state = "loading";
      try {
        const response = await window.__bluedotPanelCommand({
          type: "choose_download_directory",
          download_directory: downloadDirectory.value
        });
        if (!response || !response.ok) {
          downloadDirectory.dataset.state = "error";
          setResponseError(response, "folder_failure");
          return;
        }
        downloadDirectory.dataset.state = "idle";
        if (typeof response.download_directory === "string") {
          downloadDirectory.value = response.download_directory;
          downloadDirectory.dataset.state = "success";
          setLocalizedStatus("folder_selected", "idle");
        }
      } catch (error) {
        downloadDirectory.dataset.state = "error";
        setLocalizedStatus("folder_failure", "error");
      }
    };
    downloadDirectory.addEventListener("click", chooseDownloadDirectory);
    downloadDirectory.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      chooseDownloadDirectory();
    });
    settingsForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      saveSettings.dataset.state = "loading";
      const response = await window.__bluedotPanelCommand({
        type: "save_settings",
        browser: browserSelect.value,
        provider: providerSelect.value,
        model: modelSelect.value,
        download_directory: downloadDirectory.value,
        clear_api_key: false
      });
      if (!response || !response.ok) {
        saveSettings.dataset.state = "error";
        setResponseError(response, "settings_failure");
        return;
      }
      saveSettings.dataset.state = "success";
      renderSettings(response.settings);
      const selected = response.settings.providers[response.settings.selected_provider];
      setLocalizedStatus(
        selected && selected.has_api_key ? "settings_saved" : "settings_need_key",
        selected && selected.has_api_key ? "success" : "idle"
      );
    });
    setApiKey.addEventListener("click", async () => {
      setApiKey.dataset.state = "loading";
      setLocalizedStatus("key_prompt", "idle");
      const response = await window.__bluedotPanelCommand({
        type: "set_api_key",
        provider: providerSelect.value,
        model: modelSelect.value
      });
      if (!response || !response.ok) {
        setApiKey.dataset.state = "error";
        setResponseError(response, "key_failure");
        return;
      }
      setApiKey.dataset.state = "success";
      renderSettings(response.settings);
      setLocalizedStatus("key_protected", "success");
    });
    clearApiKey.addEventListener("click", async () => {
      // Deleting a key cannot be undone, so the first click only arms the button.
      if (clearApiKey.dataset.state !== "confirm") {
        armClearApiKey();
        return;
      }
      resetClearApiKey();
      clearApiKey.dataset.state = "loading";
      const response = await window.__bluedotPanelCommand({
        type: "save_settings",
        provider: providerSelect.value,
        model: modelSelect.value,
        clear_api_key: true
      });
      if (!response || !response.ok) {
        clearApiKey.dataset.state = "error";
        setResponseError(response, "key_delete_failure");
        return;
      }
      clearApiKey.dataset.state = "success";
      renderSettings(response.settings);
      setLocalizedStatus("key_deleted", "success");
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (form.getAttribute("aria-busy") === "true") return;
      const prompt = query.value.trim();
      if (!prompt) {
        query.setAttribute("aria-invalid", "true");
        query.dataset.state = "error";
        setSearchState("error");
        setLocalizedStatus("prompt_required", "error");
        query.focus();
        return;
      }
      panelState.query = prompt;
      saveState();
      setLoading(true);
      setLocalizedStatus("searching", "loading");
      try {
        const result = await window.__bluedotPanelCommand({ type: "search", prompt });
        if (!result || !result.ok) {
          setSearchState("error");
          setResponseError(result, "search_failure");
          return;
        }
        showResult(result);
        panelState.result = result;
        saveState();
        if (typeof result.history_index === "number") pushHistoryEntry(result.history_index);
        setSearchState("success");
        setLocalizedStatus("ready", "success");
      } catch (error) {
        setSearchState("error");
        setLocalizedStatus("search_failure", "error");
      } finally {
        setLoading(false);
      }
    });
    query.addEventListener("input", () => {
      query.removeAttribute("aria-invalid");
      query.dataset.state = "idle";
      if (form.getAttribute("aria-busy") !== "true") setSearchState("idle");
      scheduleQueryResize();
    });
    query.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
      event.preventDefault();
      form.requestSubmit();
    });
    window.addEventListener("popstate", async () => {
      const index = currentHistoryEntry();
      if (index === null) return;
      if (form.getAttribute("aria-busy") === "true") return;
      setLoading(true);
      setLocalizedStatus(
        index === baselineEntry ? "restoring_baseline" : "restoring_history",
        "loading"
      );
      try {
        const response = await window.__bluedotPanelCommand({ type: "restore", index });
        if (!response || !response.ok) {
          setSearchState("error");
          setResponseError(response, "restore_failure");
          return;
        }
        if (response.result) {
          showResult(response.result);
          panelState.result = response.result;
          if (typeof response.result.prompt === "string") {
            query.value = response.result.prompt;
            panelState.query = response.result.prompt;
            scheduleQueryResize({ shrink: true });
          }
          setSearchState("success");
          setLocalizedStatus("history_shown", "success");
        } else {
          resultSection.hidden = true;
          panelState.result = null;
          setSearchState("idle");
          setLocalizedStatus("filters_reset", "idle");
        }
        saveState();
      } catch (error) {
        setSearchState("error");
        setLocalizedStatus("restore_failure", "error");
      } finally {
        setLoading(false);
      }
    });
    query.value = typeof panelState.query === "string" ? panelState.query : "";
    if (panelState.result && panelState.result.ok) showResult(panelState.result);
    markHistoryBaseline();
    setCollapsed(Boolean(panelState.collapsed));
    scheduleQueryResize({ shrink: true });
    window.addEventListener(
      "resize",
      () => {
        setCollapsed(Boolean(panelState.collapsed));
        scheduleQueryResize();
      },
      { passive: true }
    );
    loadSettings();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
