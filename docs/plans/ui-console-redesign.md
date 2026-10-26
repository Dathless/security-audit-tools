# UI Console Redesign Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with TDD for behavior changes and one fresh whole-branch review at the end. Check off each verified task.

**Goal:** Rebuild the UI into an extensible console with three state-preserving themes, purposeful motion and consistent readable evidence.
**Architecture:** existing manifest registry + shared shell/layout/components; one React tree; central theme store applies root data-theme and semantic CSS tokens. Module hooks/API/risk behavior remain unchanged.
**Tech Stack:** React 19, TypeScript, Vite, CSS/WAAPI, native dialog, existing Selenium/pytest. No new dependency planned.
**Spec:** [approved design](ui-console-redesign-design.md), approved 2026-10-24; [interactive reference](previews/ui-console-themes.html).
**Base:** main `3056c01`; branch `codex/ui-console-redesign`.

**Status:** implementation completed on 2026-10-25. Full suite: **372 passed**; final no-env/storage case: **1 passed**; lint/build, docs and evidence checks passed. Fresh review findings fixed. Publication through a PR into main was authorized on 2026-10-26; the delivery checks are recorded in the [validation report](../testing/reports/ui-console-redesign.md). Startup Programs remains planned.

**Publication verification, 2026-10-26:** fresh complete groups passed: 271 backend + 77 browser regression + 24 theme tests, plus one separate no-env/storage test. Lint/build, evidence and local-link checks passed. Standards review found one changelog grouping error, now fixed; spec review found no actionable mismatch. Interrupted runs are excluded from passing evidence.

## Global constraints

- Technical Console default; Graphite Studio and Light Precision retain exactly the same panels, data, labels and actions. Only layout/presentation/motion vary.
- Theme switching preserves route, query/filter/sort, evidence and scan/review lifecycle; no API requests or remounts caused by theme changes.
- Preserve discovery, module IDs/routes, auth/token/Origin behavior, read-only limits and raw risk versus review semantics.
- Exact viewports: 390x844, 1024x768, 1440x900. No page-level horizontal overflow; technical table scrolling stays bounded.
- Shared semantic tokens, reduced-motion overrides, accessible controls/focus/dialog behavior. No fake production metrics or unsupported features.
- Plans stay in existing docs/plans per repository convention. No commit/push/merge until requested for this UI work.

## Review focus

1. Storage denied/invalid preference: app still starts with Technical; no flash/crash or scan request.
2. Theme change with filtering/evidence/running scan: same component state and no duplicate sockets/mutations.
3. Long paths, many owners and 20+ module names: content inspectable, navigation/search usable at every viewport.
4. Loading/empty/error/partial/permission states in Light as well as dark: readable, recoverable and identical meaning.
5. Dialog focus/Escape/theme selector and reduced motion: no hidden keyboard controls, loss of evidence or runaway animations.

## File responsibilities and interfaces

- `frontend/src/core/theme.ts`: `ThemeId`, `THEMES`, `initializeTheme(): void`, `setTheme(value: unknown): void`, `useTheme(): ThemeId`; validated localStorage, root attribute, external-store subscription. No scan app-store dependency.
- `frontend/src/design-system/components/ThemeSelector.tsx`: labeled native select, compact/full presentation, unique IDs; consumes theme store.
- `frontend/src/main.tsx`: initialize theme before createRoot.
- `frontend/src/design-system/tokens/index.css`: three-layer surfaces/action/risk/type/spacing/motion tokens for all themes; native body reset and reduced-motion gate.
- `AppShell.tsx/.css`, `NavItem.tsx/.css`: manifest-derived searchable navigation, responsive menu/dialog, status/context/actions/theme selector. Existing scanRegistry and health wiring stay intact.
- Shared `Button`, `Panel`, `PanelGrid`, `KpiCard`, `DataTable`, `ProgressBar`, `StatusBadge`, `EmptyState`, `ErrorBanner`, `ModulePageLayout` styles: consistent console surfaces and motion; layout slots/panel IDs rather than per-theme branches.
- `EvidenceDrawer.tsx/.css`: `open`, `title`, `onClose`, `children`, optional `actions`; native dialog, Escape/close/focus return and mirrored ThemeSelector.
- `PortScannerPage.tsx/.css`: compact endpoint rows; same owners/reasons/guidance/status/previous evidence available in drawer; keep hook and raw metrics.
- `FirewallCheckPage.tsx/.css`: compact profiles/rules and full evidence using shared drawer/layout; no backend/risk changes.
- `SettingsPage.tsx/.css`, `ScanHistoryPage.tsx`, `ComingSoonPage.tsx`: shared surfaces, Appearance section and consistent terminology.
- `backend/tests/test_selenium_themes.py`: controlled browser theme/state/navigation/accessibility regression; existing Selenium fixtures and upgrade seed helper.
- Existing Selenium tests: adapt approved presentation changes while preserving behavioral assertions. Docs: frontend architecture, README/index/changelog, screenshots and validation report.

## Task 1 — Theme state and preferences

- [x] Write `test_theme_defaults_persists_and_rejects_invalid_storage`, `test_theme_settings_mirrors_shell`, `test_theme_storage_denial_does_not_break_startup` in `backend/tests/test_selenium_themes.py`. Assert root IDs technical/graphite/light, full three options, persisted reload, invalid fallback and no browser errors.
- [x] RED: run `python -m pytest tests/test_selenium_themes.py -k 'defaults or mirrors or storage' --selenium -q`; expect missing ThemeSelector/root-theme assertions.
- [x] Implement theme.ts/ThemeSelector/main initialization; integrate shell and Settings selectors without replacing pages. Token palettes include every existing semantic variable.
- [x] GREEN same tests; frontend lint/build exit 0. Record evidence here.

## Task 2 — Shared console shell and components

- [x] Write browser cases for searchable manifest navigation including 20 injected future entries, keyboard menu/close/focus at 390, and three-theme panel parity at all viewports. No production fake modules.
- [x] RED focused cases: absent module search/menu/panel IDs or overflow should fail.
- [x] Rebuild tokens, shell/context bar/navigation, metric strip and shared controls/panels/table styles. Use root selectors for panel positions; keep component keys and labels. Add unique table search IDs and readable empty-filter feedback.
- [x] GREEN targeted cases, lint/build, inspect captures at target viewports. Generic module pages must inherit the surface without theme branches.

## Task 3 — Port inventory and evidence

- [x] Write `test_theme_switch_preserves_filter_evidence_and_review` with seeded TCP/UDP endpoints: filter, open full owner evidence, switch all three themes inside dialog, inspect original path/user/status/reasons, close and verify query/state. Capture request counts around switching; zero extra requests/mutations.
- [x] RED before compact rows/drawer; initial test expects the new evidence affordance.
- [x] Implement EvidenceDrawer and compact Port columns while retaining searchable full owner text. Same panel IDs `port-inventory`, `port-summary`; CSS grid positions differ by theme and stack inventory first on narrow screens. Keep review controls, provisional/legacy states, removal and before/after evidence available.
- [x] Update existing path/table-copy browser expectations to inspect full evidence rather than require all fields in an overflowing row. Do not weaken risk/review, stale-callback or scan-resumption assertions.
- [x] GREEN new state-parity test + existing upgrade and review persistence cases. No change to usePortScanner/API behavior unless a demonstrated regression requires it.

## Task 4 — Firewall, History and Settings consistency

- [x] Add theme-parity check for seeded Firewall/profile/rule evidence; verify all themes preserve risk/reason text and count. Confirm Settings Appearance does not change local token or review counts, and History retains module selection.
- [x] RED relevant affordances/layout before implementation.
- [x] Migrate profile presentation/rule inventory to shared controls/drawer, keep full fields/guidance. Style History/Settings/coming-soon pages consistently; avoid duplicate primary scan actions while preserving empty/error actions.
- [x] GREEN Firewall Selenium, review persistence and theme parity; capture long content in Light and Technical.

## Task 5 — Motion, responsive and accessible states

- [x] Add cases for reduced-motion computed styles, native dialog focus/Escape/return, loading/empty/error/partial/permission fixtures and theme switching during a running scan. Assert endpoint/risk/review data unchanged and no new socket/request caused by theme selection.
- [x] RED missing gates or inaccessible controls before fixes.
- [x] Apply shared motion tokens: small entry/disclosure/button/status transitions; progress uses scaleX, not animated width. Disable idle loops and transform motion under reduced preference. No per-row live animation storms or viewport fade hiding slow work.
- [x] Render all three themes at exact viewport sizes using CDP viewport override. Check contrast/touch/focus/overflow and long values, record observations and artifacts. Run frontend-design-direction evidence checker on truthful local JSON; no fabricated pass states.
- [x] GREEN state/motion tests, lint/build. Read every failure and fix the underlying behavior.

## Task 6 — Regression, fresh review and handoff

- [x] Run full backend `python -m pytest`, full browser `python -m pytest --selenium`, frontend `pnpm lint` and `pnpm build`; logs only in ignored .pytest_cache. Fix intentional-copy assertions separately from actual regressions.
- [x] One fresh whole-branch reviewer per executing-plans/requesting-code-review. Fix Important/Critical findings with RED→GREEN and appropriate regression; record any deferred limits explicitly.
- [x] Update current architecture/README/changelog/docs index and write `docs/testing/reports/ui-console-redesign.md`; include only seeded captures and actual test/evidence counts.
- [x] Run docs link and Git diff checks; verify no secrets/host data/new dependencies. Hand off implementation branch; no publication implied.

## Execution ledger

- Task 6 complete 2026-10-25: **372 passed, 1 existing warning (559.15s)** from `python -m pytest -q --selenium` with final Windows fixture. Includes all 271 backend tests and all 101 browser cases, no skips/errors. Extra no-env/storage configuration **1 passed (6.33s)**. Final lint/build exit 0; 33 fixture screenshots regenerated and inspected, evidence checker passes. Raw final logs: `.pytest_cache/ui-final-full.log`, `ui-final-no-env.log`, `ui-final-evidence-check.log`.
- Final: fixed denied-storage startup/save reporting — `test_all_storage_denied_keeps_settings_and_reports_save_failure` RED→GREEN with and without env token; suite 372/372.
- Final: fixed live evidence replacing owners/risk from old data on failure — disconnect/error parametrized regression RED→GREEN; suite 372/372. Hooks/backend behavior unchanged.
- Final: fixed missing protocol/action sorting (regraded Important) — two compact-inventory sort cases RED→GREEN; suite 372/372. No deferred minors; declined-to-judge list empty.
- Ruling: finish by keeping this local branch and all source/docs, per this plan's no-publication scope; do not present an integration approval menu or begin Startup Programs. Cost: work remains uncommitted and must be staged/committed explicitly before later publication. Keep approved UI plan paths stable for this handoff; mark completion here and in the docs index.

- Fixture selector + border check: **5 passed (50.66s)** including all real Firewall browser scenarios. This verifies synchronous PowerShell collection remains compatible. Rerun whole suite with this fixture; production loop remains untouched. Border test now verifies actual nonzero-width edges rather than the CSS shorthand.

- Full attempt 2026-10-25: **305 passed / 1 failed / 66 setup errors (336.34s)**. One obsolete border assertion compared the four-edge CSS shorthand to a single color despite KPI borders only on the right. Inspect only edges with nonzero width. Setup cascade traced to Windows Proactor accept failure **WinError 64** at 14:36:49, after which fixture health connections timed out; not counted as passing.
- Ruling: use Uvicorn's installed custom `asyncio:SelectorEventLoop` factory only in the Windows Selenium server to avoid the observed IOCP accept failure. Verified installed loop-factory API and synchronous Firewall collection in a thread; do not switch production runtime or add dependencies. Cost: full browser results cover selector transport, not endurance of the default Windows production loop under repeated connection teardown. Keep this explicit in the report.

- No-env GREEN: **1 passed (6.42s)**; complete storage denial no longer crashes startup/Settings, token save failure remains explicit. Frontend lint/build exit 0 after fixes; dependency manifests/lockfiles unchanged. Artifact docs audit and frontend evidence checker pass; default missing CONTRACT/TESTS/REGRESSION files remain adoption warnings, not broken links.
- Review gate complete: no Critical findings; all Important (including regraded sorting) implemented and covered by failing-then-passing browser checks. No deferred minors, no declined-to-judge rulings, no second review. Whole-suite verification still required before Task 6 is marked complete.

- Final fix pass: review cases plus compatibility **7 passed (37.69s)** after RED. Guarded getLocalToken preserves env priority and returns no token on read denial; Settings catches failed writes and never reports success. Failed live drawers close before old data becomes selectable; scan hooks unchanged. Restore separate sortable protocol/action columns, retaining compact evidence disclosure.
- No-env RED reproduced the startup crash independently (**1 failed, 17.13s**) using fully denied Storage and an explicitly empty VITE_LOCAL_TOKEN. New fixture flag affects only selected test runs; backend auth remains enabled.
- Compatibility/color assertions use the new evidence location and semantic color tokens rather than obsolete blue palette constants; JS computed colors avoid Selenium rgb/rgba normalization differences. Keep real behavior assertions (stored data, labels, sorting, raw risk) intact.

- Resume audit 2026-10-25: Task 6 was incomplete. Prior full suite was interrupted with compatibility failures; final reviewer hit a usage limit before reviewing. Follow user instruction: finish UI only; do not begin Startup Programs on this turn. Corrected report's local evidence JSON link.
- Fresh final review completed read-only: no Critical; Important findings for fully denied storage/no env token and live evidence silently reverting to old snapshot on failure. Sorting loss labelled Minor by reviewer is regraded Important: removing protocol/action grouping is an unintended functional regression for existing inventories. Declined-to-judge list empty. Fix all three in one pass, no second reviewer.
- Review RED: five failing cases (61.84s) cover save failure, live disconnect/error and protocol/action sorting. Compatibility RED separately reproduced two old inline-evidence assertions (28.41s); adapt them to the approved drawer while retaining stored note, endpoint and neutral remote-address checks. No backend API contract change.
- Ruling: guard local token reads and report persistence denial in Settings; do not invent another token store or disable authentication. Add a test-only --selenium-no-env-token fixture option to exercise the real no-environment fallback. Cost: denied-storage users must permit storage before saving a token, and receive an explicit failure instead of a false success.

- Tasks 3–5 verified: theme/state/motion/contrast suite **18 passed (85.01s)**, lint/build exit 0; native backend regression **271 passed / 95 Selenium skipped (28.94s)**. Current control-border ratios: Technical 3.821, Graphite 4.191, Light 3.464; all tested text ≥4.5 and focus ≥3.
- Final polish RED: masked-token and 22-module General-nav assertions failed; legacy assertion rerun after loading to verify the actual missing label (**1 failed, 8.04s**). GREEN **3 passed (16.82s)**. General stays outside the scrolling module list, Settings masks the input without changing its value, History labels old assessment counts without recalculating them.
- Ruling: use this plan's checked task text and execution ledger directly on Windows; the skill's shell-only workspace/commit wrappers are replaced by equivalent logged pytest commands. The UI work remains uncommitted as specified; no review range can rely on new commits. Final reviewer must include working-tree/untracked files, not just BASE..HEAD. Cost: manual ledger discipline, kept in this file.

- Task 4 and motion: RED **2 failed / 1 passed (27.39s)** for absent Firewall evidence and focus cycle escaping; GREEN **16 passed (142.37s)** across themes/Firewall, with lint/build exit 0. Native dialogs now explicitly wrap Tab/Shift+Tab; idle radar animations stop; progress uses transform.
- Rendered finish pass 1: 9 success viewport captures + 15 state captures produced; state/layout checks **8 passed**, contrast check **1 failed (40.04s)**. Technical control boundary measured 2.072:1. Increase Technical/Graphite control border luminance, then rerun all palette ratios. Static panel dividers remain subtle, controls use stronger border tokens.
- Ruling: actual captures showed Graphite summary delaying the inventory below the first viewport and excess mobile toolbar spacing. Compact the wide summary into a strip; put review select in the table toolbar; preserve identical controls/content and state. Add optional toolbar slot to the existing DataTable, rather than another table implementation.
- Ruling: remove obsolete external font requests because the approved typography uses installed/system fonts. No font package/dependency added.

- Task 3: evidence affordance RED **1 failed (18.44s)**; GREEN **18 passed (132.23s)** across themes and Port upgrade lifecycle/review races. Existing metadata/path tests inspect the new drawer, retaining all original evidence assertions. Lint found an unused startScan binding after removing duplicate actions; remove that binding in Task 4 before rerunning lint/build.
- Ruling: bounded table search accepts an optional searchText function so compact columns remain searchable by full bind/protocol/reasons without adding invisible table columns. No backend/hook changes.

- Task 1 complete: theme preference tests RED **3 failed (47.93s)**, GREEN **3 passed (16.11s)**; lint/build exit 0. Invalid IDs and denied storage recover safely.
- Task 2 complete: shell cases RED **2 failed / 3 passed (35.39s)** for missing search/menu, GREEN **8 passed (42.47s)** including preference cases and all three viewports; lint/build exit 0. Registry injection is test-only. Shared tables now have unique search labels and bounded keyboard-scroll regions.

- Ruling: keep the existing clean checkout on codex/ui-console-redesign, reusing configured Windows test/browser dependencies; main remains unchanged. Preview server only serves curated demo assets on localhost:8765.
- Ruling: user explicitly approved planning **and implementation**, so proceed inline after saving/self-reviewing this plan without another approval/menu. One fresh final reviewer remains required; no implementer delegation.
- Ruling: apply approved CSS/WAAPI motion choice, shared tokens and reduced motion rather than install a motion library for these bounded transitions. React/SSR-specific motion-foundations prescriptions are adapted to the approved Vite client design; avoid unused spring/framework scaffolding.
- Pre-flight: theme store is independent of scan state and updates root attributes; module pages keep identical tree/keys. PanelGrid identifiers feed CSS positioning and parity tests. EvidenceDrawer consumes module-owned content; core remains free of module-specific fields.
- Pre-flight: no backend/API schema changes. Existing test-token/temp-database/browser fixtures stay authoritative; screenshots use seeded records only. Final tests must still cover Firewall and existing Port lifecycle/review races.
- Plan self-review: all spec sections map to Tasks 1–6; theme API names and panel IDs consistent; all five review-focus conditions have owning browser tests. No extra approval needed; implementation proceeds.
