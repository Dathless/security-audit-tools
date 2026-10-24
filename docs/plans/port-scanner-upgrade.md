# Port Scanner upgrade — Implementation Plan

**Trạng thái:** đã triển khai và kiểm chứng. Nhánh triển khai: `codex/port-scanner-upgrade`; trạng thái công bố/tích hợp được xác nhận bằng Git và PR, không phải release được gắn tag.
**Spec:** kế hoạch người dùng phê duyệt ngày 2026-10-24; kiểm kê local, risk có bằng chứng, review độc lập severity.
**Architecture:** psutil → endpoint inventory/owners → assessment → executor/SQLite transaction → REST/WebSocket → React. Không thêm dependency, không active probe, không xác minh binary hoặc firewall correlation.
**Baseline:** main de5f27d; 61 focused tests passed during review.

## Checklist

- [x] 1. Collector/fixtures: endpoint identity v2, metadata status, all risk reasons, configuration validation, per-scan PID cache.
- [x] 2. Lifecycle/diff: constructor errors, partial inventory, versioned baseline, single-active scan and restart recovery.
- [x] 3. Review storage/API: fingerprint, expiry/suspension, atomic persistence, latest-target conflict, legacy whitelist read/delete/410.
- [x] 4. UI: endpoint rows, raw risk/review, metadata, initial/added/changed, running resume/disconnect, event buffering and Settings transition.
- [x] 5. Verification: backend, browser suite, lint/build, 1000 sockets/50 PIDs performance comparison, independent branch review.
- [x] 6. Handoff: current architecture, API/README/changelog and validation report.

## Rules and acceptance

- Each item identifies protocol, family, scoped bind address and port; owners retained; PID/name are not endpoint identity.
- Raw severity and reasons never change when reviewed. Risky loopback=warning; non-loopback=warning; risky non-loopback=danger; unknown essential identity=warning; all reasons preserved.
- Review fingerprint: endpoint + sorted executable/user owners + assessment version + severity/reasons; exclude PID/time. Missing metadata suspends persistent review and permits scan-only acknowledgement. A→B→A and complete disappearance expire review, requiring fresh acknowledgement.
- First v2 scan is initial, not mass removal. Partial scan never emits removal or becomes baseline. Old snapshots remain legacy, never reclassified.
- POST /reviews {scan_id,item_id,note?}, GET /reviews paginated, DELETE /reviews/{id}; stale target=409; old POST /whitelist=410, old list/delete retained.
- One backend process/SQLite; single Port scan, manual overlap=409, scheduled overlap skipped, abandoned running scans recovered before scheduler.
- Metadata work ≤ one Process per PID per scan; one inventory query; use oneshot. No cross-scan PID cache.

## Execution ledger

- Ruling: use the clean existing checkout on codex/port-scanner-upgrade rather than an additional worktree, reusing configured Windows Python/browser/Node dependencies; main stays unchanged.
- Ruling: use this persisted checklist/ledger instead of Bash task scripts because the approved plan is behavioral and the workspace uses PowerShell.
- Pre-flight: collector identity/assessment versions are consumed by baseline selection, review fingerprint and UI. Core extensions default to existing behavior for other modules; Port opts out of whitelist severity overrides.
- Pre-flight: module models register through existing package import before create_all. Browser fixtures must delete review rows before scans.
- Ruling: do not commit/push implementation unless explicitly requested for this feature; prior publication authorization applied to the completed documentation refactor.

- Collector TDD: 13 failed/4 passed before implementation; 17 passed after. Pipeline TDD: 8 failed before, 8 passed after. Review API TDD: 9 failed before, combined new suite 34 passed. UI TDD: 3 failed before, 3 passed after.
- Ruling: update legacy tests for explicitly approved semantics (no whitelist override, no fake port 0, versioned endpoint keys and first-scan initial). The first full backend run had 40 old-contract failures, recorded in backend/.pytest_cache/port-all-first.log; no failures are skipped.

- Final review: one fresh read-only whole-branch review found four Important issues: partial observed-change expiry, SQLite transaction held across item broadcasts, delayed review callbacks replacing newer scans, and raw/stale sidebar initialization. All entered the same RED→GREEN fix pass; no second reviewer dispatched.
- Final: fixed partial A→B→A expiry, module review summary, bounded progress and cancellation — focused regressions first had 4 failures/33 passes; after fixes the expanded integration/realtime suite had 93 passes. Item publication regression first read running/0 items, then read done/1 item after commit; the subscriber also yields and writes a separate transaction.
- Final: fixed delayed review success/error responses — initial Chrome race test failed before generation guard; both response variants passed with the guard. Metadata status and stale sidebar initialization tests each failed before display/initialization fixes. History labels and generated OpenAPI 409/410 tests also failed before their fixes.
- Ruling: re-grade metadata status, progress/cancellation and History labels as required completion work, rather than defer them as polish — the approved plan requires explicit failure status, bounded live updates, terminal lifecycle and risk/review terminology; omitting them would retain misleading or stuck states.
- Ruling: add only a manifest-owned summary serializer callback for current review counts — generic API/core does not import Port code; other modules retain stored JSON summaries. Cost: one additional optional module extension to maintain.
- Ruling: persistent reviews in partial scans expire on positively observed complete fingerprint changes, but not endpoint absence — incomplete inventory must not erase evidence of an observed owner change; otherwise A→partial B→A falsely restores trust.
- Ruling: preserve the explicit user path docs/plans/port-scanner-upgrade.md after completion instead of moving it to completed/ — keeps requested handoff links stable, costs one documented docs-layout exception.
- Ruling: retain reviewer verification limits — single-process SQLite, fixture rollback/restart and Chrome flow tests cover this scope; no claim of multi-process safety, native privilege/cross-platform inventory accuracy, disk/power-loss recovery, full accessibility audit, production FPS/history performance or binary/network authenticity. Those remain separate work, not silently verified.
- Benchmark: synthetic 1,000 sockets/50 PIDs, 5 runs, process lookup delay 0.2 ms; baseline median 613.081 ms/1,000 Process calls versus upgrade 63.565 ms/50 calls; inventory once in both. No live-host SLA.
- Gates: backend 271 passed/76 browser cases opt-in skipped; complete suite with Selenium 347 passed in 551.76s, including Firewall regression. After the final Settings-only refresh fix, 11 controlled Chrome/review-persistence cases passed in 88.50s; lint/build exit 0 again. Final Radar copy/accessibility labels were aligned with UDP observation semantics, then the seeded UI preview test and lint/build passed again. See [validation report](../testing/reports/port-scanner-upgrade.md).
- Final: fixed Settings revocation leaving an old sidebar count — new controlled Chrome case timed out before the refresh fix, then passed within the 11-case suite. This localized UI change was verified by its affected browser cases and lint/build; the entire 347-case suite was not repeated afterward.
- Documentation checks: read-only artifact audit found all local Markdown links valid; optional CONTRACT.md/TESTS.md/REGRESSION.md defaults are absent, deliberately retaining existing OpenAPI/architecture/test sources instead of adding duplicate documents. git diff --check and cached diff check passed; no dependencies, local config/token or host scan data added.
- Initial handoff before publication request: README, architecture/risk/frontend docs, future Startup plan references, testing catalog status, docs index and changelog updated. [Seeded UI screenshot](../screenshots/port-scanner-upgrade.png) contains demo data only. No deferred review findings remain; verification limits are explicit in the report. New source/doc/image files were intent-to-add for full review, without staged content or feature commits at that point.
- Publication request 2026-10-24: user authorized committing/pushing this feature and then merging into main. Publish one atomic Conventional Commit with an explicit breaking-change migration, open a PR, check its current head/mergeability/checks, then merge through the normal repository controls. No force-push or branch-protection bypass.
