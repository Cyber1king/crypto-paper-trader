# Phase 37 — Verification

**Phase type: read-only audit and planning.** No backtest, no performance
calculation, no data acquisition, no strategy/validator/dataset modification, no
AI integration, nothing staged, committed or pushed.

---

## 1. Integrity constraints — confirmation

| Restriction | Status |
|---|---|
| No backtests or performance calculations | **Held** — no `run_backtest` or `analyze` call; no metric computed for any instrument |
| No strategy modifications | **Held** — 0 tracked files modified |
| No application-code modifications | **Held** |
| No validator modifications | **Held** — `dataset.py`, `acquisition.py` and all validators read only |
| No dataset modifications | **Held** — 5 dataset digests re-verified unchanged |
| No manifest modifications | **Held** |
| No new data acquisition | **Held** — no download performed |
| No AI provider integrations | **Held** |
| No commits, pushes or staging | **Held** |
| No deletions | **Held** |
| Frozen artifacts preserved | **Held** — all 9 re-verified |
| Spent BTC holdout preserved | **Held** — digest unchanged, no re-use proposed |

**Tests were deliberately not run.** The Python suite executes backtests
internally; running it would breach the no-backtest constraint. Verification
instead relied on direct code reading and independent recomputation, which is the
stronger evidence for an audit.

---

## 2. Facts recomputed this phase

Nothing below was taken on trust from a prior report.

### 2.1 Dataset identities — all unchanged

| Dataset | SHA-256 | Result |
|---|---|---|
| `BTCUSDT_1h_Cleaned (1).csv` | `201a3b15d50a791cb5be2b755107c8303906c8fc3ca6b64e8377c9fc73ba016b` | **PASS** |
| `binance_spot_BTCUSDT_1h_202601-202608.csv` | `918153fde98e39c03eef8a7b82a2861adfdc98a080c8810e371869eb3ea22437` | **PASS** |
| `binance_spot_BTCUSDT_1h_202609-202610.csv` (**spent holdout**) | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` | **PASS** |
| `binance_spot_ETHUSDT_1h_202401-202610.csv` | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` | **PASS** |
| `ecb_reference_rates_daily_20240101_20261008.csv` | `030b48e28e3649b972fc197627161c5085387aadece91ee4a5a65a25ed3e0753` | **PASS** |

### 2.2 ETH recomputed

| Property | Recomputed | Result |
|---|---|---|
| Rows | 24,288 | PASS |
| Range | 2024-01-01 00:00 → 2026-10-08 23:00 | PASS |
| Missing intervals | **0** | PASS |
| Duplicate timestamps | **0** | PASS |
| Line endings | LF only, no CR | PASS |
| Span arithmetic | 1012 × 24 = 24,288 | PASS |
| Archives vs publisher `.CHECKSUM` | 41/41 match | PASS |
| Rows re-derived from archives | 24,288 | PASS |
| **Numeric mismatches** | **0** | PASS |
| Epoch unit distribution | 8,784 ms + 15,504 µs | PASS |

### 2.3 Phase 35 provenance correction still in force

| Assertion | Count | Result |
|---|---|---|
| 2024 sidecars assert MILLISECONDS | 12/12 | PASS |
| Later sidecars assert MICROSECONDS | 29/29 | PASS |
| Sidecar total | 41 | PASS |

Verified with an **assertion-aware** method that distinguishes the archive's
actual assertion from the previous text quoted inside a `CORRECTION` block. A
naive substring search initially mis-reported 41 — a checker limitation, not a
data defect, and the same artefact noted in Phase 35 §4.

### 2.4 Forex dataset is not OHLC — verified

| Check | Result |
|---|---|
| Header is `date,pair,rate,rate_type,source` | PASS |
| No open/high/low/close column (regex over header) | PASS |
| No volume column | PASS |
| Every row has exactly 5 fields | PASS |
| Pairs | EURUSD, GBPUSD, USDJPY | PASS |

### 2.5 Code facts established this phase

| Fact | Evidence | Result |
|---|---|---|
| `validate_dataset()` performs exactly 6 assertions | `dataset.py:33-72` read directly | Confirmed |
| It lacks an interval-spacing check | Regex probe | Confirmed |
| It lacks a price-positivity check | Regex probe | Confirmed |
| It lacks session/holiday/DST checks | Regex probe | Confirmed |
| It lacks bid/ask checks | Regex probe | Confirmed |
| It lacks research-window overlap checks | Regex probe | Confirmed |
| **`config.asset` is never validated against data** | Only non-declaration reference is `replay.py:363`, passing the label into replay context; **0 enforcing references** | Confirmed |
| Strategy thresholds are all scale-relative | `level * (1 + buffer)`, `abs(close-level)/level <= tolerance`, `slow_ma * strength` | Confirmed |

---

## 3. Findings that correct or extend prior phases

| # | Finding |
|---|---|
| **N1** | **The strategy is fully scale-invariant and nothing validates `asset` against the dataset.** ETH would run mechanically with no code change and no error. This was not previously stated plainly and materially changes the risk picture: governance is the *only* control on an ETH run |
| **N2** | The strongest anti-reuse protection — the spent BTC holdout — rests on a **recorded sentence in a report**, not on an enforced code guard. `normalize_source` checks only the hard-coded 2024–2025 window and never consults `consumed_windows` |
| **N3** | `validate_dataset()` accepts an all-zero price row (`0,0,0,0` satisfies `high>=low` and both containment checks). `acquisition` enforces positivity; the native load path does not |
| **N4** | Volume semantics are documented but **never declared in any artefact and never enforced** |
| **N5** | ETH 2026 has **never been examined for performance**, so — unlike BTC — a genuinely unexamined ETH window exists. This is the one favourable readiness finding |
| **N6** | Independent re-derivation (the strongest provenance evidence in the chain) has been done by hand **twice** and is not automated |

---

## 4. Files created (4, all new, all under `experiments/phase37/`)

| File | Purpose |
|---|---|
| `DATA_APPROVAL_CHECKLIST.md` | ETH checklist, BTC readiness, forex readiness |
| `INSTRUMENT_READINESS_MATRIX.md` | Per-instrument status ledger |
| `VALIDATION_GAPS.md` | Contract coverage and missing controls |
| `VERIFICATION.md` | This file |

**No other file was created, modified, renamed, moved or deleted.**

---

## 5. Git state — exact

| Field | Value |
|---|---|
| `HEAD` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Branch | `main` |
| `origin/main` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Modified tracked files | **0** |
| Deleted tracked files | **0** |
| Staged files | **0** |
| Commits ahead of `origin/main` | **0** |
| Commits or pushes performed | **none** |
| Untracked before this phase | **267** |
| Untracked after this phase | **271** (+4, all under `experiments/phase37/`) |

Breakdown of the 4 new untracked entries: all under
`research_engine/experiments/phase37/`.

---

## 6. Read-only inspection performed

| Source | What was read |
|---|---|
| `data/phase33/` | ETH dataset, ECB dataset, both manifests, acquisition log, all 41 provenance sidecars |
| `data/oos/` | BTC primary, OOS 2026-01..08, spent holdout |
| `crypto_paper_lab/dataset.py` | All 6 assertions, read directly |
| `crypto_paper_lab/acquisition.py` | Research-window guard, `epoch_to_datetime`, overlap constants |
| `crypto_paper_lab/strategy.py` | Config, scale-relative thresholds |
| `crypto_paper_lab/replay.py` | `config.asset` usage at line 363 |
| `crypto_paper_lab/costs.py` | `spread_rate` forced to 0.0 |
| `crypto_paper_lab/walkforward.py` | Warm-up rule, integrity validator scope |
| `crypto_paper_lab/windowstats.py` | Exposure refusal |
| `experiments/phase29/` | Pre-registration |
| `experiments/phase30/` | All 4 result files |
| `experiments/phase33–36/` | Acquisition report, audit, correction, architecture, governance, roadmap |

No raw archive was re-extracted for its own sake; archives were read directly to
re-derive rows.

---

## 7. Limitations

| # | Limitation |
|---|---|
| L1 | **No performance was calculated for any instrument.** Whether a preregistered question would be answerable is untested |
| L2 | ETH 2026's untouchedness is inferred from the fact that no ETH performance was ever computed — **not** confirmed by inspecting a result, because none exists |
| L3 | **Whether ETH 2026 yields enough trades is unknown.** ETH's realised trade rate has never been measured, and measuring it requires a backtest. The repository's own floor is ~50 trades |
| L4 | Validation gaps were identified by reading code, not by adversarial test. Each gap is shown **absent**, not proven exploitable |
| L5 | The test suite was deliberately not run, since it executes backtests internally |
| L6 | No FX venue, licence or session calendar was evaluated; no data downloaded |
| L7 | Provider, session-calendar and licensing details remain **[VERIFY]** items from Phase 36 |
| L8 | This audit assessed **integrity and readiness**, not scientific merit. **Readiness is not permission** |

---

## 8. Outcome

| Instrument | Status | Reason |
|---|---|---|
| BTC/USDT | **BLOCKED** | No untouched validation data; cannot be fixed internally |
| ETH/USDT | **INCOMPLETE** | Data fully verified Grade A; governance artefacts missing |
| EUR/USD | **BLOCKED** | No market OHLC; no session/DST library |
| GBP/USD | **BLOCKED** | Same |
| USD/JPY | **BLOCKED** | Same; also lower precision |

**Nothing is READY FOR REVIEW. Nothing is RESEARCH APPROVED.** The term
`RESEARCH APPROVED` does not appear as a status anywhere in these deliverables.

**Integrity approval remains separate from research approval** — closing every
validation gap would make a dataset integrity-complete, not evaluable.

**The spent BTC holdout remains retired and was not reused.**

The standing conclusion is unchanged: no reliable profitability has been
established for this strategy, and nothing in this phase alters it.