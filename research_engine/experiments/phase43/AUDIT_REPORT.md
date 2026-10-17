# Phase 43 — Repository and Change Audit

**Date:** 2026-10-09
**Method:** Read-only inspection. Nothing was deleted, moved or overwritten.

---

## 1. Repository state

```
branch            main
HEAD              dccebbd53ee8365474345506db9099b13356b53c
origin/main       dccebbd53ee8365474345506db9099b13356b53c
ahead / behind    0 / 0
staged            none
tracked modified  11 files, +330 / -11
untracked         292
```

### Untracked breakdown

| Area | Files | Assessment |
|---|---|---|
| `data/phase33/` | 215 | Research data + provenance. **Keep** |
| `data/oos/` | 30 | Consumed OOS windows. **Keep** |
| `data/*.json` | 2 | Registry + per-bar index. **Keep** |
| `experiments/` | 38 | Phase reports. **Keep** |
| `src/` | 4 | New guard/identity modules. **Keep** |
| `tests/` | 3 | New test files. **Keep** |

`data/phase33/` is 8.2 MB: the merged ETH dataset, raw archives (164 files),
41 provenance sidecars, and acquisition metadata. All legitimate research input.

---

## 2. Phase 39–42 reports verified against source

| Claim | Result |
|---|---|
| `researchguard.py`, `researchindex.py`, `dataset_identity.py`, `intervals.py` exist | Confirmed |
| `consume_reservation`, `assert_series_permitted`, `candle_fingerprint` exist | Confirmed |
| Guard tests pass | Confirmed — 189 passed |
| No backtest or performance API in guard/validation tests | Confirmed |
| ETH reservation unspent | Confirmed |

### One discrepancy found

**`researchguard.__all__` was stale.** It listed 15 names, omitting three public
functions added in Phase 40: `assert_series_permitted`, `consume_reservation`
and `candle_fingerprint`. A caller relying on `__all__` for introspection or
`from … import *` would not see them.

Impact was low — direct imports worked — but `__all__` is documentation as well
as mechanics, and it was wrong about three of the module's most important
functions. **Fixed**, with tests added so it cannot drift again.

---

## 3. Dead code

Static analysis (definition referenced nowhere, including its own file) found
three items:

| Location | Item | Disposition |
|---|---|---|
| `data.py` | `optional_market_data_key()` | **Kept.** Pre-existing, reads an env var. Out of scope to remove; flagged for review. |
| `dataset_identity.py` | `identity_covers()` | **Removed.** Superseded — its check is now wired into `validate_dataset(identity=…)`, where it actually runs. |
| `researchguard.py` | `_partially_matches()` | **Removed.** Dead wrapper; its logic lives in `_indexed_window()`, which is called. Its documentation was merged into the live function rather than lost. |

A broader scan flagged many private helpers as "unreferenced"; all were
verified as false positives — they are called from their own module, which the
first scan excluded.

---

## 4. Documentation

### 3,859 lines of phase reports across 57 files

Checked for duplication by comparing shared substantial lines between the
Phase 39–42 reports: **no meaningful duplication found.** Each report covers a
distinct phase and cross-references rather than restates.

### Genuine conflict: three readiness matrices

| Document | ETH status | Forex status |
|---|---|---|
| `phase37/INSTRUMENT_READINESS_MATRIX.md` | **INCOMPLETE** | BLOCKED |
| `phase41/MARKET_READINESS_MATRIX.md` | **NOT APPROVED** | BLOCKED |
| `phase42/FINAL_READINESS_MATRIX.md` | **BLOCKED** | BLOCKED |

This is a real inconsistency, not a cosmetic one. Phase 37's own vocabulary
defines `INCOMPLETE` as "data-side prerequisites met; governance artefacts
missing" — which described ETH accurately *at that time*. Phase 42 rated it
`BLOCKED`, which is also defensible under a stricter reading where four of six
required conditions are unmet.

**BTC and forex agree across all three.** Only ETH differs, and the difference
is a definitional drift rather than a factual disagreement.

**Recommendation:** adopt Phase 42's stricter reading and treat Phase 37 as a
point-in-time record. A single canonical matrix with explicit dates would
prevent this recurring.

---

## 5. Generated artifacts

| Path | Status |
|---|---|
| `.pytest_cache/` (5 files) | Ignored by `.gitignore:55` |
| `__pycache__/` (3 dirs, 87 files) | Ignored by `.gitignore` |

Nothing generated is at risk of being committed. `.gitignore` already covers
Python caches.

One near-miss observed during the audit: a stale `.pyc` briefly masked a source
edit, causing a test to report an error string that no longer existed in the
source. Python's mtime check should prevent this; it was resolved by
re-verifying against source rather than the compiled artifact. Worth noting
because debugging against a stale `.pyc` wastes time.

---

## 6. Code-quality issues found

### 6.1 A real contradiction in the reservation writer

`_consume_reservations()` set `used: true` but left `status: "RESERVED"`,
producing a window that was simultaneously available and spent. No code
checked this, so it went unnoticed.

Fixed by Phase 45: consumption now sets `status: "USED"` alongside `used:
true`, and `registry_schema` refuses the contradictory combination.

### 6.2 Two conflicting status checks in `assert_evaluation_permitted`

A duplicated `status != "RESERVED"` check meant a spent window was reported as
a status problem rather than as spent — a less actionable message. Consolidated
into one check, ordered so "already been used" fires first.

### 6.3 Declared timeframe was not bound to actual data

`validate_dataset` accepted `expected_interval_seconds` as an optional
caller-supplied number. A caller could declare timeframe `1h` and validate
5-minute data by simply omitting the parameter. `identity_covers()` existed to
catch this but was never called.

Fixed by Phase 45: `validate_dataset(identity=…)` derives the interval from the
declaration and refuses contradictory explicit arguments.

---

## 7. Prioritized cleanup plan

Nothing below was executed except where marked **done in Phase 45**. This is a
plan for future work, ordered by risk addressed per unit of change.

### P1 — Correctness (all done in Phase 45)

| # | Item | Status |
|---|---|---|
| 1 | Stale `researchguard.__all__` | **done** |
| 2 | `status`/`used` contradiction in consumption writer | **done** |
| 3 | Duplicate status check masking the spent-window message | **done** |
| 4 | Declared timeframe not bound to actual bar spacing | **done** |
| 5 | Dead `identity_covers`, `_partially_matches` | **done** |
| 6 | Registry metadata never validated | **done** |

### P2 — Documentation (not done; requires a decision)

| # | Item | Note |
|---|---|---|
| 7 | Reconcile the three readiness matrices | Needs a ruling on ETH's status; not a code fix |
| 8 | Add a canonical `READINESS.md` with dates | Would prevent recurrence |
| 9 | Consider a short INDEX pointing at phase reports | 57 files is navigable but not discoverable |

### P3 — Hygiene (not done)

| # | Item | Note |
|---|---|---|
| 10 | Review `optional_market_data_key()` | Reads `MARKET_DATA_API_KEY`; no live-exchange code exists. Decide whether an unused API-key hook is appropriate in a paper-only project. |
| 11 | `.gitignore` for `research_engine/artifacts/` | Not currently needed |
| 12 | Prune `__pycache__` before any future commit | Currently ignored; harmless |

### Explicitly NOT recommended

- **Deleting raw archives or provenance sidecars.** They are the evidence base
  for Grade A provenance claims. 8.2 MB is a fair price for reproducibility.
- **Deleting consumed datasets.** They are what proves windows were spent.
- **Collapsing phase reports.** Each records a distinct phase; compression would
  destroy the audit trail.

---

## 8. Preserved

Verified unchanged before and after this audit:

- BTC primary, BTC holdout, Phase 29 pre-registration, Phase 30's four result
  artifacts, ETH dataset — all SHA-256 matches.
- ETH reservation: `RESERVED` / `used: false` / `preregistration_id: null`.

No file was deleted or overwritten during the audit itself.

---

## 9. Verdict

**PASS.** Three real defects found (stale `__all__`, a
`status`/`used` contradiction, and an unbound declared timeframe), all fixed and
tested in Phase 45 with tests that fail without the fix. One documentation
conflict identified and left for a human decision rather than silently
resolved. Nothing deleted. All frozen artifacts and the ETH reservation
verified intact.