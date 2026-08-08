# Design QA — справка Blue Dot Agent

> **Обновление.** Нативное окно Tkinter заменено модальным оверлеем внутри Shadow DOM панели
> (`bluedot_agent/help_window.py` удалён, содержимое перенесено в `bluedot_agent/help_content.py`).
> Разделы ниже описывают предыдущую реализацию и сохранены как история проверки; скриншоты
> `design-qa-help-*.png` относятся к ней же. Актуальные проверки — в разделе
> «Interaction and technical checks».

**Source visual truth**

- The source screenshots were supplied during the design review and are not part of the repository.
- Source pixels: 451 × 70, density 1×.
- Target: existing expanded panel header; add a question-mark control before Settings while preserving the established control geometry and palette.
- Content annotation: remove the supported-filter paragraph, replace local installation steps with provider registration/key links, and document free-model limits.

**Implementation evidence**

- Header: `design-qa-panel-header.png`
- Header comparison: `design-qa-header-comparison.png`
- Native help window: `design-qa-help-window.png`
- Provider registration and key links: `design-qa-help-keys.png`
- Free-model limits: `design-qa-help-limits.png`
- Browser viewport: 1280 × 800 CSS px at device scale factor 1.
- Header crop: 339 × 61 px. The implementation uses the current 340 px responsive panel width; the supplied historical crop is 451 px wide, so comparison is limited to title/control proportions rather than full-frame width.
- Help window: requested client size 760 × 680 logical px; captured outer window 776 × 719 px at 1× density.
- States: panel expanded/help closed; panel collapsed; native help open on “О проекте”; help window verified topmost.

**Full-view comparison evidence**

- The comparison image shows that the title, baseline, dark header surface, rule, button borders and spacing remain consistent with the supplied header.
- The added `?` control uses the same 44 px geometry and state styling as Settings and Collapse. The existing title remains visible without wrapping or truncation.
- The native window uses the panel’s navy surfaces, cool-gray borders, white typography and purple accent; all primary content fits without horizontal overflow.

**Focused region comparison evidence**

- `design-qa-header-comparison.png` is the focused control-region comparison because button alignment and title clearance are the fidelity-critical details.
- The full native-window capture is readable at original size, so no additional crop was required for typography or copy review.

**Required fidelity surfaces**

- Fonts and typography: Bahnschrift remains the display face; Segoe UI is used for body and controls. Heading weights, line height and wrapping are readable and consistent with the existing panel.
- Spacing and layout rhythm: three header controls preserve equal dimensions and gaps. The help window has consistent 18–24 px outer spacing, tab alignment, content padding and a persistent bottom action.
- Colors and visual tokens: dark navy background, blue-gray surfaces/borders, light text and purple interaction accent follow the current product palette with adequate contrast.
- Image quality and asset fidelity: the executable’s existing Blue Dot microphone icon is used as the native window icon; no replacement illustration or placeholder asset was introduced.
- Copy and content: the filter inventory and already-completed local installation steps are absent. Registration/key creation, first search, free-access qualifications, provider-specific limit semantics, key storage and recovery guidance match the official provider pages and `README.md`.

**Findings and comparison history**

- First pass — [P2] the bottom “Закрыть” action was outside the visible window because the expanding notebook consumed the pack layout first.
  - Fix: reserve the footer at the bottom before packing the expanding notebook.
  - Post-fix evidence: `design-qa-help-window.png` shows the complete content area and visible “Закрыть” button.
- Content revision first pass — [P2] tabs opened at the insertion cursor, hiding their title and introductory paragraph above the viewport.
  - Fix: move the insertion mark and scroll position to `1.0` after populating every tab.
  - Post-fix evidence: `design-qa-help-keys.png` and `design-qa-help-limits.png` both open at their titles and expose the first relevant link without manual scrolling.
- Final pass: no actionable P0, P1 or P2 differences remain.

**Interaction and technical checks**

- Clicking `?` opens the in-page overlay and sends no command over the Playwright binding.
- The overlay is a viewport-wide fixed layer inside the panel’s Shadow DOM, so the 340 px host does not clip it.
- The help control hides with the other expanded-only controls when the panel is collapsed.
- Escape, a backdrop click and the “✕” action all close the overlay and return focus to `?`.
- Tab buttons expose `role="tab"`/`aria-selected`; ArrowLeft and ArrowRight move between sections.
- Browser console and page-error capture after help click and collapse/expand: no errors.
- Link targets are HTTPS pages on official Google, Groq, OpenRouter and Mistral domains and open with `target="_blank" rel="noopener noreferrer"`.
- Automated suite: 112 tests passed.

**Follow-up polish**

- [P3] The native scrollbar intentionally retains the active Windows/Tk theme instead of imitating a browser scrollbar.

final result: passed
