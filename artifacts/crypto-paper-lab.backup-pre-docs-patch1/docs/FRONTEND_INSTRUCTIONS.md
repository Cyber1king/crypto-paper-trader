-----BEGIN FRONTEND_INSTRUCTIONS-----
# Frontend Project Instructions

Scope: artifacts/crypto-paper-lab only. Paper trading and research display only.

## Stack (confirmed from inspection reports)
- React 18 + Vite, wouter routing, @tanstack/react-query, recharts, Tailwind v4 (CSS-first, configured in src/index.css)
- shadcn-style primitives in src/components/ui/. Radix Dialog is available directly.
- API access through the PaperApi class in src/lib/api.ts; the Orval client in lib/api-client-react is used for health only
- Same-origin requests through the Vite proxy
- The workspace is NOT a Git repository

## Observed facts about the current source
- src/App.tsx has one real route ("/") rendering pages/dashboard.tsx, plus a 404 fallback. AppShell wraps the Switch (Batch 1).
- Dashboard owns its own sticky header, health badge (test ids health-online and health-offline), PaperOnlyBanner, mode selector, and market chart. Do not duplicate them.
- Selected mode is local state inside Dashboard. There is no shared mode or market context.
- MarketQuery has only limit, start, and end. There is no timeframe parameter; asset and timeframe come from the dataset metadata. Do not build a timeframe selector.
- src/components/state.tsx already provides PaperOnlyBanner, LoadingPanel, ApiUnavailablePanel, ErrorPanel, EmptyPanel, StatRow, Panel, UnavailableModePanel, and Rule.
- The ui/index.tsx barrel does not re-export Sheet. components/sidebar.tsx does not exist; ui/sidebar.tsx does, but index.css defines no sidebar tokens, so it is not used.
- no-mock-data.test.ts reportedly scans an exact list of 18 live files (LIVE_FILES). New files are outside its scope, so they rely on review.
- tsconfig.base.json enables incremental, so a plain typecheck would write a .tsbuildinfo file.

## Conventions
- The API is the only authority for data. Do not derive P&L or performance in the UI.
- Every data view handles loading, error, empty, and unavailable states explicitly.
- Reuse existing components before adding new ones. Extend existing files by small patches.
- Keep data-testid values unique and consistent with existing usage.
- No fabricated prices, balances, or performance. Missing data is labeled Unavailable or Demo.
- Simulated account data is always labeled paper or simulated.
- No new dependencies without written justification.
- Never invent API fields or endpoints; use only fields confirmed in src/lib/api.ts.

## Hard boundaries
- Frontend files only. No changes to backend, research engine, reservation or approval state, test allowlists, exclusion audits, or execution logs.
- No real-money trading and no exchange order execution.
- No invented endpoints. Missing endpoints get a proposed contract marked awaiting backend approval; the UI shows an Unavailable state meanwhile.
- No restricted tests, backtests, optimization, walk-forward or yearly analysis, performance evaluations, or access to protected datasets, excluded results, or protected evidence.
- Do not modify tests, allowlists, shared configuration (including tsconfig.base.json), or the no-mock-data test to accommodate new files.
- No Git initialization, commit, push, or destructive Git operation without separate explicit owner approval.

## Verification policy (owner approvals as of 2026-10-20)
- Approved: the typecheck only, run as: npm run typecheck -- --incremental false (the override avoids writing a .tsbuildinfo file; shared config is not touched). Stop if composite is enabled in the config chain.
- Every typecheck run compares a SHA-256 manifest of the app folder, the backup folder, lib/api-client-react, and root tsconfig files before and after, and reports any difference.
- Disabled until separately approved: build, tests, lint, dev server.
- Routine steps within these rules are delegated to Claude; the owner is asked only for genuine blockers (a failed stop condition, an API or architecture decision, a destructive change, or any Git operation).

## Batch workflow
1. Claude proposes a batch with exact paths and full file contents or precise patches, plus an OpenCode instruction.
2. The OpenCode instruction runs in phases: read-only checks, targeted backup of every existing file to be modified (outside the source tree, SHA-256 verified), a gate, source edits (new files written and read back before existing files are replaced), the permitted typecheck, then a read-back report.
3. Any failed check stops the run. Nothing is repaired automatically.
4. The owner returns OpenCode's report; Claude reviews it against the proposal and updates FRONTEND_PROGRESS.md.
5. Claude lists the files changed per batch. Git operations are authorized separately by the owner.

## Rollback (manual, owner-authorized only)
- For a modified file, copy its backup from the backup folder over the current file. For a new file, delete it.
-----END FRONTEND_INSTRUCTIONS-----