-----BEGIN FRONTEND_PROGRESS-----
# Frontend Progress Log

## Current status (2026-10-20)
- Batch 1 (shell): applied per OpenCode report; NOT yet verified. Do not treat the frontend as compiling or working until a typecheck succeeds.
- Typecheck: approved with the incremental override; first plain attempt was correctly stopped because tsconfig.base.json enables incremental.
- Batch 2 (paper portfolio and trade journal pages reusing standard-mode panels and hooks): scope chosen; source extraction in progress; nothing written.

## Batch plan
| Batch | Scope | Status |
|---|---|---|
| 1 | Shell: desktop sidebar, mobile drawer | Applied, unverified |
| 2 | Paper portfolio (/portfolio) and trade journal (/journal) pages reusing existing standard-mode panels and hooks | Source extraction in progress |
| 3 | Market analysis page and top bar (asset and timeframe from market metadata) | Not started |
| 4 | Research reports and research-safety status | Blocked on response shapes and API contract |
| 5 | Strategy signals | Blocked on API contract |

## Batch 1: applied (per OpenCode report)
Files:
- Created: src/components/app-shell.tsx (about 174 lines)
- Modified: src/App.tsx (AppShell import and wrapper around Switch; routing, QueryClientProvider, 404 fallback, and BASE_URL handling unchanged)
- Backup: artifacts/crypto-paper-lab.backup-pre-batch1/src/App.tsx, SHA-256 0ef53a301c520885869458302c7d92416a345ceb2079d9a66ecc0aa538e41a80, 1024 bytes, matches the original
- New App.tsx SHA-256: 149cc0389f3af44b70e28ed081c1801c82bb0e788f588e52beb09cc0cb5186fe

Design:
- Plain aside plus Radix Dialog drawer. No use of ui/sidebar, ui/sheet, or index.css changes. Dashboard untouched.
- Overview is the only live link. The other five screens are disabled and labeled Planned until their routes exist.
- Top bar and PAPER / SIMULATED strip deferred: Dashboard already carries the header, banner, and health badge, and asset and timeframe are available only from market data.

Verification performed:
- Read-only pre-checks, hash comparison of the backup, and read-back of both files (all reported MATCH).
- Not yet performed: typecheck, build, tests, browser check.

## Known risks and open items
- Compile status unknown until the typecheck runs.
- no-mock-data guard: reportedly scans an exact list of 18 files, so new files are outside its scope; full test text still being collected.
- Whether any test renders App is unconfirmed; sidebar text or test ids could collide with such a test.
- Layout and drawer behavior have not been viewed in a browser.

## Unresolved API dependencies
- Strategy signals: no confirmed endpoint; contract not yet drafted.
- Research-safety status: no confirmed endpoint; contract not yet drafted.
- Research reports: four research endpoints exist; response shapes not yet reviewed.
- Trades: pagination and filter support not yet confirmed.

## Next recommended step
Run the typecheck, then write Batch 2 from the extracted source.
-----END FRONTEND_PROGRESS-----