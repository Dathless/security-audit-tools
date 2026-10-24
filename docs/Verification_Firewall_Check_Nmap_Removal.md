# Verification — Nmap removal and Firewall Check v1

## Delivered behavior

- Port Scanner uses psutil only, including TCP LISTEN, UDP, IPv4/IPv6 and process metadata. Legacy `scan_mode: nmap` becomes socket mode with a warning; existing database fields and history remain readable.
- Firewall Check reads the effective Windows policy store and associated rule filters. It evaluates profiles and broad inbound rules, keeps evidence/manual guidance and fails explicitly on missing permissions/data or timeout.
- Four module REST endpoints, shared scan serialization, persistence, progress/replay and completed/full diff baselines are implemented.
- Firewall UI and module-specific history are active. Transport failure can be retried; global busy state follows backend health after navigation.
- Both shared WebSocket endpoints now require the local token and reject foreign browser origins. Browser tokens are passed as subprotocols, never URL parameters. Existing non-browser clients can use X-Local-Token.

## Evidence

| Check | Result |
|---|---|
| Baseline before implementation | 169 passed, 62 browser tests skipped |
| Port/config tests after Nmap removal | 28 passed; legacy-config regression was observed failing first |
| Firewall collector matrix | 36 initial tests passed; subsequent native PowerShell/duplicate-identity cases also passed |
| Real Windows collector | 3 profiles and 508 enabled rules initially; an independent associated-filter query returned the same rule count |
| Firewall browser workflows | 4 passed, including transport close and leaving a running scan |
| WebSocket/API auth regressions | Seven cases failed before the fix; 31 relevant tests passed after it |
| Existing browser regressions | Focused rerun: 15 passed after correcting Selenium API, DOM synchronization, uppercase text, selectors and test isolation |
| Stronger whitelist persistence | Passed against the same port over two actual scans |
| Full backend with line tracing | 221 passed, 66 browser tests intentionally excluded for this measurement |
| Frontend ESLint + production build | Passed |
| Postman CLI against isolated live backend | History status/envelope/items/page-size assertions passed, exit 0 |
| Final complete browser-inclusive run | **287 passed, 0 failed, 0 skipped**, one existing warning; 398.98 seconds |
| Pre-push rerun on 2026-10-24 | **287 passed, 0 failed, 0 skipped**, one existing warning; 401.46 seconds. Frontend lint/build and diff checks also passed |

Line coverage was measured with Python's standard-library trace and a full-path filter (to distinguish project scanners from json.scanner). No dependency was added:

| Runtime module | Line coverage |
|---|---:|
| Firewall collector/classification | 100% |
| Port collector/classification | 100% |
| Executor | 100% |
| Shared serializer | 100% |
| Firewall routes | 98% |
| Port routes | 99% |
| Shared WebSocket | 93% |

## Review and limits

An independent review found three material issues: unauthenticated shared WebSockets, a stuck scan after transport failure, and stale global busy state after leaving the module. All three received regression tests and fixes. The empty-rule PowerShell path was also tested with deterministic fake cmdlets rather than the host firewall.

The first full browser run had 11 failing legacy UI tests; their failure details remain in backend/.pytest_cache/final-all.log. A second run exposed three remaining history/navigation synchronization assumptions, which were corrected and verified independently before the final full run. No failures are hidden by a skip marker.

Final command, run from backend/: `python -u -m pytest --selenium -v --basetemp .pytest_cache/verified-all --tb=short --durations=10 --junitxml=.pytest_cache/verified-all.xml`. Full evidence is in backend/.pytest_cache/verified-all.log and verified-all.xml. Final `pnpm lint`, `pnpm build`, and `git diff --check` passed.

Pre-push evidence is in backend/.pytest_cache/pre-push-native-20261024.log and pre-push-native-20261024.xml. This complete rerun used the same suite with a 45-second diagnostic timeout and its own basetemp; native execution was required after the sandboxed attempt stalled before the first API test. Generated logs and XML are not committed.

All implementation/checklist tasks are complete. The proposed next feature, Startup Programs, has a design and implementation plan in Plan_Startup_Programs.md; it is not implemented by this change.

The collector audits configuration; it does not establish Internet reachability or resolve every interacting firewall condition. The coverage figures are line coverage, not branch or JavaScript coverage. Chrome was exercised; Firefox was not. One existing FastAPI/Starlette TestClient deprecation warning remains; dependencies were not upgraded as part of this task.

Implementation was initially left uncommitted for review. On 2026-10-24 the user authorized commits and a push of `codex/firewall-check-nmap-removal`; the publication checklist is in Implementation_Checklist.md. The existing whitelist Settings panel and Selenium selectors are included separately so the committed browser suite has its required UI. Local configuration, tokens, databases and generated output remain excluded. New documentation is force-added individually under the existing docs/ ignore rule.
