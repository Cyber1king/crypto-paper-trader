# Phase 64 — Verification

**Date:** 2026-10-10

## Deliverables
- `REPORT.md` — licence remediation audit and ordered checklist.

## Checks performed

| Check | Method | Result |
|---|---|---|
| Phase 62 ECB artifact checksum | `Get-FileHash -Algorithm SHA256` | **MATCH** `424859b8...0343` |
| Artifact size | `Get-Item .Length` | **107,678 bytes** (matches capture record) |
| Artifact presence | filesystem | found at `experiments/phase62/evidence/` |
| Python package licence field | `pyproject.toml` read | **absent** |
| `LICENSE` file | repository-wide tracked-file search | **absent** |
| Root npm licence scope | `package.json` + `pnpm-workspace.yaml` | MIT scoped to npm workspace only |
| Binance attribution | 8 provenance sidecars L46 | present |
| Governed state changed | registry re-parse | **No** |

## Commands executed

`
Get-FileHash -Algorithm SHA256 research_engine/experiments/phase62/evidence/ecb_disclaimer_copyright_2026-10-10T13-24-13Z.html
Select-String -Path research_engine/pyproject.toml -Pattern 'license'
git grep -Iln 'CC BY-NC-SA' -- '*.md' '*.txt'
`

**Exit codes:** all `0`. **Test counts:** none run, therefore none claimed.

## Unresolved
B1 licence choice, B2 registry correction, B4 provenance remain owner decisions.
No governed correction was applied.

## Next phase safe to proceed
Yes. Phase 65 (data provenance audit) is read-only inspection of data files.
