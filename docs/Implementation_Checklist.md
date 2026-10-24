# Implementation checklist — Firewall Check and Nmap removal

Plan: `docs/Plan_Firewall_Check_Nmap_Removal.md`

- [x] 1. Remove Nmap; verify legacy configuration and port scan regression tests.
- [x] 2. Implement read-only Windows collector, validation, classification and tests.
- [x] 3. Add module API, shared serialization, persistence, WebSocket and reliable diff baseline.
- [x] 4. Add Firewall Check UI and module-specific scan history.
- [x] 5. Run backend suite, frontend lint/build and Selenium; fix verified regressions.
- [x] 6. Compare a real Windows snapshot, review changes and document evidence.
- [x] 7. Propose the next feature and save its design and implementation plan (requested during execution).

## Decisions and evidence

- Execution uses `superpowers:executing-plans`, `superpowers:test-driven-development`, `postman:api-engineer`, `postman:api-testing`, `ecc:verification-loop`, and `superpowers:verification-before-completion`.
- Ruling: keep the current checkout on a new feature branch, preserving existing uncommitted UI/test work; a clean worktree would omit that work. No commits or pushes are part of this implementation request.
- Ruling: use this persistent checklist instead of the skill's Bash task scripts: the saved plan is a behavior specification, not their numbered brief format, and this repository uses PowerShell. Verification commands and results are recorded below.
- Pre-flight: backend scan summaries feed REST, WebSocket, frontend KPIs and history. Preserve `total_open` for Port Scanner and add optional firewall counts. Shared serializers must retain the original envelope and pagination.
- Pre-flight: executor applies whitelist to every module. Firewall exposes no whitelist API; stable item keys serve identity/diffing only.

## Verification results

- Baseline: 169 passed, 62 Selenium tests skipped; one existing FastAPI TestClient deprecation warning.
- Nmap regression: new legacy-config test failed before the change; 28 port/config tests passed afterward.
- Collector: 36 tests passed, including malformed JSON, missing evidence, permissions, timeout, Unicode, profile/rule risk matrix and non-Windows handling.
- Real read-only collector: 3 profiles, 508 enabled rules, 145 warnings, 366 items without a v1 finding; completed in about 9 seconds.
- Ruling: invoke the bundled fixed PowerShell source with `-Command` rather than `-File`, since Windows blocks script files under the current ExecutionPolicy. Do not change ExecutionPolicy. Test command safety explicitly.
- Ruling: query filters through their associated enabled rules. Bulk store queries are denied on this Windows account; association queries return complete data without extra privilege.
- Backend suite after API integration: 210 passed, 62 Selenium skipped.
- Frontend production build and ESLint passed.
- Selenium Firewall Check: 2 passed, using the real Windows collector and a separate temporary database; verified navigation, profiles, rules search and module history.
- Test harness fixes: use a temporary database/test token, launch Vite directly for reliable teardown, and write backend logs to a file rather than an undrained PIPE that can block the server. Header assertions account for CSS uppercase rendering.
- Final independent review found an inherited unauthenticated WebSocket data channel plus two new hook lifecycle issues. Seven auth/Origin/handshake regressions failed before the fix; 31 WebSocket/API tests passed afterward. Token now uses a WebSocket subprotocol, not a URL parameter. Foreign browser origins are rejected.
- Ruling: secure both shared WebSocket endpoints as part of the feature: exposing new firewall program paths and rule scopes through an unauthenticated global channel would violate the local-token guarantee. Existing non-browser clients can use X-Local-Token; browsers use sec-audit/token subprotocols. Clients must update their handshake.
- Browser regressions reproduced a stuck Firewall Check after transport close and a stuck global busy label after leaving a running scan. Handle transport failures and reconcile global busy state with backend health.
- Four Firewall Check browser tests passed after the review fixes.
- Added a real PowerShell script test with fake cmdlets: zero enabled rules must not trigger unassociated filter queries; the test failed before the guard and passed afterward.
- First complete browser-inclusive run: 273 passed, 11 failed. All failures were existing Selenium assumptions: invalid get_attribute signature, uppercase text, mixed caption color tokens, stale DOM handles, overly broad selectors, and shared test data. Fixed these at the test/harness boundary; the focused rerun passed 15 tests.
- Strengthened whitelist persistence to find the same port after a second scan instead of conditionally doing nothing; its isolated test passed.
- Backend coverage run: 221 passed, 66 browser tests skipped intentionally for this measurement. Standard-library trace measured Firewall collector 100%, Port collector 100%, executor 100%, shared serializer 100%, firewall routes 98%, port routes 99%, shared WebSocket 93% line coverage. No runtime or test dependency was added. This is line coverage, not branch coverage.
- Postman CLI live history request against the isolated backend passed its status/envelope/items/page-size assertions (exit 0); no workspace setup or publication.
- Second full rerun: 284 passed, 3 failed. History navigation still relied on previous test data; two navigation checks read a stale DOM/health state. The revised test cases seed their own history and wait for backend completion or the target page/title; all three passed together.
- Final complete rerun: **287 passed, 0 failed, 0 skipped**, one existing TestClient deprecation warning, 398.98 seconds. Command: `python -u -m pytest --selenium -v --basetemp .pytest_cache/verified-all --tb=short --durations=10 --junitxml=.pytest_cache/verified-all.xml`. Evidence: backend/.pytest_cache/verified-all.log and verified-all.xml.
- Final frontend `pnpm lint` and `pnpm build` passed; `git diff --check` passed.
- Next-feature proposal saved as docs/Plan_Startup_Programs.md, using superpowers:writing-plans. It contains the design, alternatives, Windows source boundaries, API/UI contracts and task/test checklist; no Startup Programs code was implemented.
- Ruling: leave the feature branch and all source changes uncommitted for review. This request authorized implementation and verification, not integration/publication; the prior no-push constraint remains in effect.

## Publication checklist — 2026-10-24

The user subsequently authorized professional commits and a push. This supersedes the earlier no-push ruling; publish the feature branch without merging main.

- [x] Review scope, remote and credential patterns; keep local configuration, tokens, databases and generated files excluded.
- [x] Include the existing whitelist Settings panel and Selenium selectors as separate commits because the browser suite depends on them.
- [x] Re-run the complete browser-inclusive suite: 287 passed, 0 failed, 0 skipped, one existing warning, 401.46 seconds. Frontend lint/build and both staged/unstaged diff checks passed.
- [x] Prepare five focused Conventional Commit messages and explicit staging lists, including the contributor guide and next-feature plan.

The first sandboxed test attempt stalled before the first API test and was interrupted. The complete native run passed with Chrome and localhost servers: `python -u -m pytest --selenium -v -o faulthandler_timeout=45 --basetemp .pytest_cache/pre-push-native-20261024 --tb=short --durations=5 --junitxml=.pytest_cache/pre-push-native-20261024.xml`. Log and XML remain under backend/.pytest_cache/ and are excluded from commits.

Publication destination: origin/codex/firewall-check-nmap-removal. Verify the pushed branch SHA against local HEAD; do not merge into main or force-push.
