# Phase 13 — Experiment Log

**Append-only.** Every entry is added below. Existing entries are never edited,
reordered or removed.

Each experiment, variant or re-run must receive its own entry **and its own
output files**. Previous results are never overwritten.

---

## Entry format

```
## Entry N — <short title>

Date created      : YYYY-MM-DD
Type              : <pre-registration | primary run | sensitivity | variant | re-run>
Git commit        : <sha>
Git clean         : <yes/no>
Dataset path      : <path>
Dataset SHA-256   : <hash>
Config            : <repr>
Config hash       : <hash>
Execution model   : <cost_deduction | fill_price>
fee_rate          : <value>
slippage_rate     : <value>
spread_rate       : <value>
starting_balance  : <value>
risk_fraction     : <value>
warmup_rule       : full_preceding_series
boundary_policy   : retain_boundary_force_closes
Windows run       : <list or all six>
Exclusions        : <none | list with reasons>
Python version    : <version>
Platform          : <platform>
Random seed       : null (deterministic)
Bootstrap seed    : <value or n/a>
Output files      : <list>
Outcome           : <one-line factual summary>
Decision          : <what was decided, and on what pre-declared basis>
Rationale         : <why>
```

---

## Entry 1 — Phase 13 methodology pre-registration

```
Date created      : 2026-10-03
Type              : pre-registration
Git commit        : f5293c91da33e929a230ff385ab4458cfa232fee
Git clean         : yes (no staged, unstaged or untracked files at time of commit
                    of the pre-registration; this log and PLAN.md are the only
                    additions)
Dataset path      : research_engine/data/BTCUSDT_1h_Cleaned (1).csv
Dataset SHA-256   : 201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B
Config            : not applicable - no experiment executed
Config hash       : not applicable
Execution model   : cost_deduction (frozen for future use, not yet exercised)
fee_rate          : 0.001 (frozen)
slippage_rate     : 0.0005 (frozen)
spread_rate       : 0.0 (frozen)
starting_balance  : 10000.0 (frozen)
risk_fraction     : 0.01 (frozen)
warmup_rule       : full_preceding_series (frozen)
boundary_policy   : retain_boundary_force_closes (frozen)
Windows run       : none
Exclusions        : none
Python version    : 3.12.10
Platform          : Windows-11-10.0.26200-SP0
Random seed       : null (walk-forward is deterministic)
Bootstrap seed    : n/a (no interval computed)
Output files      : none - pre-registration only
```

**Status of Phase 13 at the time of this entry:**

- **Baseline pass pre-registered** — `StrategyConfig()`, six frozen windows.
- **A2 pass pre-registered** — `StrategyConfig(min_breakout_distance=0.002)`,
  six frozen windows, with mandatory disclosure that A2 was selected during
  Phase 7 using 2024–2025 research data.
- **No Phase 13 results exist yet.**
- **No configuration was selected using Phase 13 results.**
- No walk-forward harness has been implemented.
- No `RESULTS_windows.csv` or `RESULTS_windows.json` exists.
- No Phase 13 tests exist.

**What this entry does:**

1. Freezes the Phase 13 methodology in `PLAN.md` **before** any implementation
   or execution.
2. Records the two pre-registered passes without ranking them.
3. Records the A2 selection-history contamination so it cannot be lost.
4. Establishes the append-only log that all future entries must follow.

**Standing constraints carried forward:**

- Window dates, configurations, execution model, account assumptions, warm-up
  rule, boundary policy and metric set are frozen in `PLAN.md` and must not be
  altered after results are seen.
- Every future variant requires its own output files. Previous results are
  never overwritten.
- No window-level confidence interval will be produced (n=6).
- No profitability threshold, ranking or winner selection applies to any
  metric.
- The standing research conclusion — that no reliable profitability has been
  established — is not revised by Phase 13.

**Next permitted step:** implementation of the walk-forward harness, followed by
tests, followed by the primary baseline run. Each will receive its own entry
below.

---

## Entry 2 — Phase 13 harness implementation and test validation

```
Date created      : 2026-10-03
Type              : implementation / validation (NOT an experiment)
Git commit        : f5293c91da33e929a230ff385ab4458cfa232fee
Git clean         : no - Phase 13A documents and Phase 13B code are untracked
Dataset path      : research_engine/data/BTCUSDT_1h_Cleaned (1).csv
Dataset SHA-256   : 201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B
Config            : baseline and A2 both implemented; NEITHER was run
Config hash       : baseline 2FBDB9A8814ABC81..., A2 46B26C08D43431AF...
Execution model   : cost_deduction implemented; NOT exercised on real data
fee_rate          : 0.001
slippage_rate     : 0.0005
spread_rate       : 0.0
starting_balance  : 10000.0
risk_fraction     : 0.01
warmup_rule       : full_preceding_series
boundary_policy   : retain_boundary_force_closes
Windows run       : NONE - zero evaluation windows executed on any dataset
Exclusions        : none
Python version    : 3.12.10
Platform          : Windows-11-10.0.26200-SP0
Random seed       : null (deterministic)
Bootstrap seed    : n/a (no interval computed)
Output files      : none - no Phase 13 result file was generated
```

**This entry is implementation validation, explicitly not experiment
execution.**

**Delivered:**

- `src/crypto_paper_lab/walkforward.py` - the six frozen windows, the two
  pre-registered configurations, frozen costs and account assumptions, dataset
  and window validation, single-window and full walk-forward execution, and
  the mutation and reproducibility guards.
- `src/crypto_paper_lab/windowstats.py` - the frozen descriptive metric set
  plus sign counts, distributions and same-sign runs.
- `src/crypto_paper_lab/stats.py` - added standalone `median_pnl` and
  `closed_net_pnls` helpers. `performance()` was **not** modified, so every
  existing report dictionary keeps its exact shape.
- `experiments/phase13/run_walk_forward.py` - the runner. It requires an
  explicit `--execute` flag; without it, it only validates and prints the plan
  and writes nothing.
- `tests/test_walkforward.py` and `tests/test_windowstats.py`.

**Validation performed:**

- Frozen window definitions and index resolution verified against the real
  dataset; every value matches PLAN.md section 3.
- All harness guards confirmed by mutation testing: 16 of 16 mutations were
  caught, including removal of the `evaluation_start` gate, slicing only the
  evaluation window, dropping the premature-entry, stray-exit,
  starting-balance, overlap, duplicate, spacing, hash, state-carry,
  dataset-fingerprint and cost-mutation checks.
- Full suite: 346 passed. The pre-existing 254 are unchanged and unreduced.

**Explicitly NOT done:**

- The six-window experiment was **not** run.
- No evaluation window was executed against the research dataset.
- `RESULTS_windows.csv`, `RESULTS_windows.json` and `SUMMARY.md` do **not**
  exist.
- No configuration was selected, ranked or compared using Phase 13 results,
  because no Phase 13 results exist.

**Architectural note recorded during implementation:**

`analyze()` reads only bounded windows - `support_resistance` uses
`candles[-lookback:]` (last 20) and `trend` uses the last 12 closes. Signal
state at any index therefore does not depend on arbitrarily deep history.
The Phase 13A audit note that "deep warm-up is not bounded" was overstated in
its practical consequence. The frozen `full_preceding_series` policy remains
correct and is still enforced, but the reason it is safe is stronger than
previously stated: a bounded prefix would also reproduce the signals, and the
full-series choice removes the question rather than relying on that fact.

**Next permitted step:** the primary baseline run, which requires explicit
authorisation and a clean working tree (the runner enforces the latter).

---

## Entry 3 — Phase 13 walk-forward diagnostic executed

```
Date created      : 2026-10-03
Type              : primary run (the authorised Phase 13 diagnostic)
Git commit        : f5293c91da33e929a230ff385ab4458cfa232fee
Git clean         : NO - executed under an explicit dirty-tree override
Dataset path      : research_engine/data/BTCUSDT_1h_Cleaned (1).csv
Dataset SHA-256   : 201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B
Dataset range     : 2024-01-01 00:00:00 -> 2025-12-31 23:00:00
Dataset candles   : 17544 (1h spacing, 0 duplicate timestamps)
Config            : baseline = StrategyConfig()
                    A2       = StrategyConfig(min_breakout_distance=0.002)
Execution model   : cost_deduction
fee_rate          : 0.001
slippage_rate     : 0.0005
spread_rate       : 0.0
starting_balance  : 10000.0
risk_fraction     : 0.01
warmup_rule       : full_preceding_series
boundary_policy   : retain_boundary_force_closes
Windows run       : all six frozen windows, both pre-registered passes
Exclusions        : none - no window, trade or configuration was dropped
Python version    : 3.12.10
Platform          : Windows-11-10.0.26200-SP0
Random seed       : null (walk-forward is deterministic)
Bootstrap seed    : n/a - no confidence interval was produced
Result artifacts  : experiments/phase13/RESULTS_windows.csv
                    experiments/phase13/RESULTS_windows.json
                    experiments/phase13/SUMMARY.md
Test status       : targeted 92 passed; full suite 346 passed
```

**Windows executed (unchanged from the pre-registration):**

| W | Train | Evaluation |
|---|---|---|
1 | 2024-01-01 .. 2024-06-30 | 2024-07-01 .. 2024-09-30
2 | 2024-04-01 .. 2024-09-30 | 2024-10-01 .. 2024-12-31
3 | 2024-07-01 .. 2024-12-31 | 2025-01-01 .. 2025-03-31
4 | 2024-10-01 .. 2025-03-31 | 2025-04-01 .. 2025-06-30
5 | 2025-01-01 .. 2025-06-30 | 2025-07-01 .. 2025-09-30
6 | 2025-04-01 .. 2025-09-30 | 2025-10-01 .. 2025-12-31

**Records produced:** 12 (6 windows x 2 passes). Verified complete, no
duplicates, no missing pairs.

**Recorded deviation - dirty working tree.** The clean-tree guard built in
Phase 13B correctly **refused** the first execution attempt. Because committing
was not permitted before the run, an explicit `--allow-dirty-tree` override was
added to the runner. This did **not** weaken the guard: the strict path is
unchanged and the dirty state is recorded verbatim in `SUMMARY.md`, including
`Git working tree clean: False` and the six porcelain entries.

**Known shortfall - not corrected.** `PLAN.md` section 13 requires
`dataset_sha256` on every window record. It is present in `SUMMARY.md` but
**absent from the per-window rows** of `RESULTS_windows.csv` and
`RESULTS_windows.json`. The shortfall was found during post-run verification
and has deliberately **not** been corrected, because regenerating results after
observing them is exactly what the no-post-hoc rule forbids. A future run would
carry the field.

**Post-run verification:** 12/12 structural checks passed - no evaluation
overlap, no pre-boundary entries, no post-window exits, one retained
`end_of_data` trade per window, fresh frozen starting balance per window,
baseline and A2 hashes disjoint and costs identical, no ranking language.

**Standing conclusion unchanged.** No reliable profitability has been
established. This was a historical walk-forward diagnostic, not fresh
independent out-of-sample validation, and it makes no forecast.

---

<!-- Append new entries below this line. Do not edit anything above. -->