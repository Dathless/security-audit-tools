# UI Console Redesign — Design

Status: approved by the user on 2026-10-24, with instruction to plan and implement. Default theme: **Technical Console**. This describes the target frontend; completion is recorded in the [implementation checklist](ui-console-redesign.md). The interactive [preview](previews/ui-console-themes.html) uses demo data and no backend connection.

## Intent and selected direction

Rebuild Security Audit's interface into a modern, compact workspace that remains readable as more modules arrive. The current shared shell and manifest discovery are useful; oversized radar allocation, wide nowrap tables, weak hierarchy, inconsistent controls and duplicated actions need redesign.

Alternatives presented: Graphite Studio (quiet dark), Light Precision (light), Technical Console (technical dark/amber). The user selected Technical Console, then explicitly requested **all three as switchable themes**, with identical displayed functionality/content. Theme differences may include layout positions, colors, animation, decoration, background and graphics. A theme must never replace a panel with different information or remove a feature.

## Scope and invariants

- Redesign shared shell/navigation, tokens, controls, layouts, tables, evidence presentation, empty/loading/error states and motion. Apply consistently to Port Scanner, Firewall Check, History, Settings and coming-soon pages.
- Keep existing API/auth, collector/risk/review logic, scan lifecycle, registry discovery and route IDs. This is not a backend redesign or a new module implementation.
- Keep risk separate from acknowledgement. No new security scores, fabricated activity feeds, host/traffic metrics or unsupported actions.
- One React component tree and one set of module pages across themes. Same panel IDs, content, controls, labels, data and tab sequence. Layout uses shared slots/CSS grid; themes do not select alternative page implementations.
- Switching themes preserves route, selected endpoint, query/filter, sorting, pagination, scroll where feasible, in-flight scan and review state. It neither remounts module pages nor sends scan/review/API requests.

## Theme contract

| Theme | Appearance | Default wide panel order | Motion |
|---|---|---|---|
| Technical Console — default | Neutral near-black, hard fine dividers, amber action/accent, technical mono metadata, restrained instrument grid | Inventory wide left; summary right | Short precise movement, scan-linked sweep, minimal entrance stagger |
| Graphite Studio | Charcoal/graphite, teal action accent, softer edges, quiet depth | Summary strip above inventory | Softer easing, small fades/translations |
| Light Precision | Warm-white/slate, deep-blue action accent, crisp separators, restrained blueprint marks | Summary left; inventory wide right | Fast fades, very small movement |

The above positions are wide-screen defaults. At narrower widths all themes stack inventory before summary; evidence remains available through the same accessible drawer/dialog. No theme hides summary, radar, findings, review controls or owner details. Decorative graphics carry no additional data.

Risk colors are semantic across themes (danger/red, warning/orange, safe/green), always paired with text/icons. Technical amber is an action/selection accent, not a risk signal. Each palette must pass contrast checks separately.

Theme selection: labeled control in the shell, mirrored under Settings → Appearance. Exactly three choices, no unrequested automatic/system mode. Default Technical; persist a validated ID in localStorage. Invalid/unsupported stored IDs or unavailable storage fall back safely to Technical. Apply the saved theme before first render to limit flashing. No backend preference endpoint, credentials or scan content in storage. Language remains the existing Vietnamese copy with established module names.

## Shared architecture

- Keep React 19/Vite/TypeScript and existing hash routes/manifest discovery. Extend shared components rather than add per-theme copies.
- Small central theme catalog/type + selection store/hook; root `data-theme` controls semantic tokens and layout variants. Keep presentation separate from scan app state where practical. New modules inherit the shell/tokens/motion through ModulePageLayout.
- Tokens: primitives → semantic surfaces/text/action/risk/focus → component aliases. Include spacing, type, density, radius, borders and motion tokens. Avoid separate hardcoded palettes inside modules.
- Shared components: module header/status/action slots, compact metric strip, panel layout, accessible search/select/buttons, data table, evidence drawer, progress/state feedback and theme selector. Existing components may be evolved/renamed only with all callers/tests updated.
- Use native platform/CSS capabilities for the preview. Production motion library choice is left to the builder: prefer CSS/WAAPI for these bounded transitions; add `motion` only if the planned shared lifecycle/exit animations justify its cost. Apply motion-foundations principles (tokens, transform/opacity, reduced motion), adapting React/SSR-specific prescriptions to this Vite client app.

## Shell and module growth

- Compact context bar, one clear primary scan action, scan/backend state with text. Remove duplicate scan actions from the same viewport while preserving recovery/empty-state actions where useful.
- Searchable, scrollable module navigation generated entirely from manifests. Active modules and coming-soon items are clearly distinguished. No hardcoded module IDs/order in the shell.
- Wide desktop: full sidebar; smaller desktop/tablet: compact rail or drawer with full-name access; narrow viewport: labeled menu button and accessible navigation drawer. Search and scrolling must accommodate 20+ module names without clipping or hiding general navigation/status.
- Do not create an Overview/dashboard or command palette merely for decoration. Do not show fake module capabilities. Existing coming-soon modules remain coming-soon.

## Page composition

**Port Scanner:** concise header + last-result/scan context, metric strip, endpoint inventory as primary surface, same summary/radar panel across themes. Compact rows prioritize risk, endpoint/protocol/bind, primary owner/count, review and change state. Full owners/exe/user/create time/field statuses, all reasons/guidance and prior evidence live in an accessible evidence drawer. All data remains available, not truncated without a way to inspect it. Review/revoke stays one mutation followed by refresh. Raw severity and review are visually distinct.

**Firewall:** compact Domain/Private/Public profile presentation, rule inventory and evidence using the same components. Preserve all profile/rule data, guidance and read-only limits. Avoid presenting configured rules as proven effective reachability.

**History:** clear module filter, time/status/counts and existing navigation. Match current risk terminology and distinguish legacy data. **Settings:** sections for connection, Appearance, modules, reviews and legacy whitelist; theme choice must not reset connection/token or invoke scan actions. Token remains local and is never rendered in design artifacts/screenshots.

**Data density:** initial target body ~14px, technical data ~13px, small metadata ≥12px; use tabular numbers and monospace only where useful. Use progressive disclosure instead of shrinking everything or forcing every field into nowrap cells. Pagination/virtualization choices remain implementation decisions; do not add backend APIs or virtualization dependencies without evidence.

## Motion and accessibility

- Motion communicates navigation, disclosure, scan progress and action feedback. Static graphics for idle backgrounds; no perpetual ambient blinking, parallax or unnecessary counters.
- Shared duration/easing/distance tokens, with theme overrides. Typical interactions 120–220ms; optional small entrance stagger capped in total duration. No per-row animation storms for live inventory or theme changes.
- Animate transform/opacity; avoid animating layout dimensions or `transition: all`. Theme layout changes must not block controls, remount pages or steal focus.
- `prefers-reduced-motion: reduce` disables transforms, sweeps, stagger and loops; use immediate changes or opacity ≤200ms. Progress text/value still communicates state.
- Keyboard access, visible focus, accessible names, semantic table/form controls, drawer focus return and Escape handling. Modal drawers trap focus; a wide-screen nonmodal evidence panel does not. If a modal blocks the global theme control, mirror the same ThemeSelector inside it so theme switching preserves open evidence. Minimum 44px touch targets for key controls; normal text ≥4.5:1 contrast, control boundaries/focus ≥3:1. No color-only status.

## Content-state contract

| State | Visible feedback and next action |
|---|---|
| Loading | Stable skeleton/placeholder geometry and descriptive status; no invented values |
| Empty | Identify missing scan/results; offer supported scan/filter reset action |
| Error/disconnect | Specific existing error and retry/reload; no stuck spinner or silent stale result |
| Partial | Keep available evidence, explicit incompleteness; do not imply absence/safety |
| Success | Finished timestamp/counts, current review state and supported next actions |
| Permission | Distinguish access_denied/gone/unknown metadata; existing safe recovery guidance, no automatic elevation |

## Verification and acceptance

- Test all three themes at **390x844**, **1024x768**, **1440x900**. No page-level horizontal overflow; bound technical table scrolling and keep primary actions reachable. Check long paths, long module names, multi-owner data and large inventories.
- Across themes, assert identical panel identifiers/content/actions and risk/review values. Switch while filtering, showing evidence and running a scan: state, focus intent and API call count remain correct. Test persistence, invalid ID, storage denial and reduced motion.
- Cover every content state above with controlled browser fixtures; keep captures free of tokens/host scan data. Reuse existing Selenium setup. Check keyboard/focus, touch targets and contrast, including theme control and drawers.
- Frontend lint/build; complete backend/Selenium regression as appropriate to shared UI changes, including Firewall and stale-WebSocket/review scenarios. Record actual commands/results and screenshot observations; do not relabel old-copy test expectations as behavioral failures.
- Use frontend-design-direction's local evidence checker for rendered viewports/content states, plus docs links/diff checks. Update architecture/frontend, README/changelog and a dedicated validation report.

## Checklist and handoff

- [x] Inspect current shell, shared components, registry, module pages and test constraints.
- [x] Record chosen direction and three-theme content-parity requirement.
- [x] Produce interactive three-theme preview; fresh builder-check found nothing important left unanswered.
- [x] Preview check: 3 themes × 3 window sizes, panel/content parity, no page overflow, filter/evidence preserved on switching, reduced motion and no browser errors. This is a design-preview check, not application acceptance.
- [x] User approval of this design; then write the implementation plan.
- [x] Implement shared shell/tokens/themes/components, migrate module pages and add purposeful motion.
- [x] Verify states/theme parity/accessibility/responsiveness and regressions; document results. Completed locally 2026-10-25: [validation report](../testing/reports/ui-console-redesign.md), 372 passing tests and a separately passing no-env/storage configuration.

Builder-owned details: exact spacing/type/palette adjustments for contrast and Vietnamese text fit, responsive breakpoints within the target viewports, CSS/WAAPI versus a justified motion library, component file organization, and table rendering/paging technique. No commit/push/merge is implied by this new UI request.

Preview images: [Technical](previews/ui-console-technical.png), [Graphite](previews/ui-console-graphite.png), [Light](previews/ui-console-light.png). This historical preview demonstrates Port Scanner only; the implementation now covers all existing module/general pages and real scan lifecycle as recorded in the validation report. Demo navigation is not the application itself. Publication remains a separate step.
