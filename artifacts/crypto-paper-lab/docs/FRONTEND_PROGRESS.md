# Frontend Progress Log

## Current status (2026-10-20)
- Batches 1 to 5 are applied per OpenCode reports. Each was typechecked with exit code 0 using: pnpm exec tsc -p tsconfig.json --noEmit --incremental false
- All seven target screens exist and are linked in the sidebar: Overview (/), Market analysis (/market), Paper portfolio (/portfolio), Trade journal (/journal), Strategy signals (/signals), Research reports (/research), Research safety (/safety).
- NOT verified in a browser or by tests. Do not treat the frontend as working until those succeed. Build, tests, lint and the dev server have not been run; each needs separate owner approval.
- The workspace is not a Git repository; nothing has been committed.

## Batch plan
| Batch | Scope | Status |
|---|---|---|
| 1 | Shell: desktop sidebar, mobile drawer | Applied; typechecks |
| 2 | Paper portfolio (/portfolio) and trade journal (/journal) reusing existing standard-mode panels and hooks | Applied; typechecks |
| 3 | Market analysis (/market) with a read-only context strip | Applied; typechecks |
| 4 | Research reports (/research) and research safety (/safety) reusing existing research panels | Applied; typechecks |
| 5 | Strategy signals (/signals, last engine signal only) and an API contract proposal for signal history | Applied; typechecks |
| Next | Owner browser check, decision on named frontend test files, decision on Git | Pending |

## Batch 1: shell
- Created src/components/app-shell.tsx; modified src/App.tsx (AppShell wraps the Switch; routing, QueryClientProvider, 404 fallback and BASE_URL handling unchanged).
- Backup: artifacts/crypto-paper-lab.backup-pre-batch1/src/App.tsx (SHA-256 0ef53a301c520885869458302c7d92416a345ceb2079d9a66ecc0aa538e41a80, 1024 bytes).
- Plain aside plus Radix Dialog drawer; no use of ui/sidebar, ui/sheet or index.css changes; Dashboard untouched.
- A global top bar was deferred: Dashboard already carries the header, banner and health badge, and asset and timeframe are only available from market data.

## Batch 2: portfolio and journal
- Created src/components/standard-page.tsx, src/pages/portfolio.tsx, src/pages/journal.tsx; modified src/App.tsx and src/components/app-shell.tsx. Backup: artifacts/crypto-paper-lab.backup-pre-batch2.
- Pages reuse the existing Standard-mode panels and hooks with no new data logic, no new dependencies and no derived figures. Loading, error and unavailable states come from the existing panels.

## Batch 3: market analysis
- Created src/components/market-context-bar.tsx and src/pages/market.tsx; modified src/App.tsx and src/components/app-shell.tsx. Backup: artifacts/crypto-paper-lab.backup-pre-batch3.
- Reuses MarketChart and useMarket (limit 200). Asset, timeframe and market type are read from the API market metadata and shown read-only. No support or resistance lines are drawn here because those come from the replay.

## Batch 4: research pages
- Created src/pages/research.tsx (76 lines) and src/pages/safety.tsx (38 lines); modified src/App.tsx and src/components/app-shell.tsx. Backup: artifacts/crypto-paper-lab.backup-pre-batch4.
- The reports page shows the existing overview, instrument explorer, provider and evidence panels. The safety page shows the existing governance panel. Props mirror the calls already made by the Dashboard; the pages render no controls and add no data logic.
- Assumption to confirm in a browser: the governance panel is the right content for research-safety status.

## Batch 5: strategy signals and contract proposal
- Created src/pages/signals.tsx (53 lines) and docs/API_CONTRACT_PROPOSALS.md (34 lines); modified src/App.tsx (46 lines) and src/components/app-shell.tsx. Backup: artifacts/crypto-paper-lab.backup-pre-batch5.
- The signals page reuses LastSignalPanel and ReplayProgressPanel inside the Standard-mode frame. It shows only the engine's last signal and says that no history exists. No new data logic, no new dependencies, no derived figures.
- docs/API_CONTRACT_PROPOSALS.md proposes a read-only signal-history endpoint, marked awaiting backend approval. Nothing in the frontend calls it.
- Reference after Batch 5: src/App.tsx SHA-256 D0B18341F25C02748E6B0B1F5ACED4732419E56C05F8B058315B0C0B48F06736; src/components/app-shell.tsx SHA-256 7CF3A86E6FD853B7466C44E35611997BD5874B67E964215762876209A8346C1A; 118 files under the app folder excluding node_modules.

## Verification log
- 2026-10-20: typecheck after each of Batches 1 to 5, each exit code 0 (OpenCode reports, some summarized). File counts, line counts and hashes were cross-checked against the proposed text. Build, tests, lint and the dev server were not run.

## Known risks and open items
- Nothing has been viewed in a browser or run under tests.
- no-mock-data.test.ts reportedly scans an exact list of 18 live files (LIVE_FILES), so new files are outside its scope and rely on review.
- Whether any test renders App is unconfirmed; sidebar text or test ids could collide with such a test.
- The replay is stepped by code inside the Dashboard page, so a running replay may stop advancing while the user is on another page. Not yet confirmed in a browser.
- OpenCode reports have often been summaries or replays of earlier reports, and its docs edits have been unreliable (stray delimiter lines, appends instead of rewrites). This file and FRONTEND_INSTRUCTIONS.md were rewritten from known-good text to remove them.
- Backup folders artifacts/crypto-paper-lab.backup-pre-batch1 to backup-pre-batch5 remain beside the app folder; keep them out of any commit.

## Unresolved API dependencies
- Strategy signal history: no endpoint exists. The proposal is in docs/API_CONTRACT_PROPOSALS.md, awaiting backend approval. The engine's last signal is already available through the replay state.
- Research status: four read-only endpoints exist and are consumed through existing hooks; no new endpoint was needed.
- Trades: pagination and filter support not confirmed.

## Next recommended step
Owner browser check of all seven pages, a decision on running named frontend test files, and a decision on whether to create a Git repository.