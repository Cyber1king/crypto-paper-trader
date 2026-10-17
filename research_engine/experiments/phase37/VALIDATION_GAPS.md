# Phase 37 — Validation Gaps

**Read-only audit.** Missing controls are **documented only**. Nothing was
implemented.

---

## 1. What `validate_dataset()` actually checks

Verified by reading `research_engine/src/crypto_paper_lab/dataset.py:33-72`
this phase. Six assertions, no more:

| # | Assertion | Line |
|---|---|---|
| 1 | dataset contains no candles | ~37 |
| 2 | invalid high/low range (`high >= low`) | ~41 |
| 3 | invalid open price (`low <= open <= high`) | ~50 |
| 4 | invalid close price (`low <= close <= high`) | ~59 |
| 5 | negative volume | ~64 |
| 6 | timestamps strictly increasing | ~70 |

It is a **structural sanity check**, not a market-data contract.

---

## 2. Gaps between `validate_dataset()` and the Phase 36 data contract

Phase 36 defined contracts C1–C14. Mapped against what exists:

| Contract | Requirement | Exists? | Where it actually lives |
|---|---|---|---|
| C1 | Row count, first/last, interval verified | **partial** | `walkforward.validate_dataset_integrity` checks count/edges/spacing, but **only against the frozen 2024–2025 constants** (`:257-316`) — not a general contract |
| C2 | No duplicates, no non-monotonic order | **yes** | `dataset.py:70` |
| C3 | On expected interval boundary | **no** in `dataset.py` | Spacing exists in `walkforward` and `acquisition` (`missing_hours`) |
| C4 | OHLC valid **and all prices strictly positive** | **partial** | OHLC relations yes; positivity **no** (a zero or negative price with a valid high/low range passes) |
| C5 | Volume finite, non-negative, **semantics declared** | **partial** | Non-negative yes; finite no; **semantics declared nowhere** |
| C6 | Every gap classified closure vs anomaly | **no** | Does not exist |
| C7 | Every row re-derivable from a checksummed source | **no** | Performed manually in Phase 34/35, **not automated** |
| C8 | Publisher digest matched, or local-only stated | **no** | Manual at acquisition time |
| C9 | Licence, attribution, redistribution recorded | **no** | In manifests, not in validation |
| C10 | Provenance manifest with retrieval time and URL | **no** | Manual |
| C11 | Zero overlap with consumed windows | **partial** | `acquisition.normalize_source` guards the 2024–2025 research window (`:396-399`); it does **not** consult `consumed_windows` |
| C12 | Session/holiday/DST validation | **no** | **Zero `dst` occurrences repo-wide** |
| C13 | Volume semantics named precisely | **no** | Does not exist |
| C14 | Bid/ask present or explicitly absent | **no** | Does not exist |

**Coverage: 1 fully met, 4 partial, 9 absent.**

---

## 3. Specific missing controls

### 3.1 Price positivity

`dataset.py` checks `high >= low`, `low <= open <= high`, `low <= close <= high`.
A row with `open = 0, high = 0, low = 0, close = 0` satisfies all three.

**Missing:** an explicit `> 0` check on all four price fields. `acquisition`
`_check_row` **does** enforce positivity (`acquisition.py:297-312`), so this gap
exists only on the `project_native` load path.

### 3.2 Finite-value checks

Neither `dataset.py` nor the loaders appear to reject `inf` or `NaN` explicitly.
An `inf` price would satisfy `high >= low`.

**Missing:** an explicit finiteness check on every numeric field.

### 3.3 Volume semantics — the highest-consequence gap

No artefact in the repository records, for any dataset, whether volume is
**centralised**, **tick**, **quote** or **absent**.

This matters concretely: Phase 33 recorded the rule *"tick volume must not be
represented as centralized exchange volume"*, and the architecture forbids
synthesising spread — but **nothing enforces either**. Both are documentation, not
code.

**Missing:** a mandatory `volume_semantics` field on every dataset and a
registry-level enum, plus a validator that refuses a dataset with undeclared
semantics.

### 3.4 Session / holiday / DST

Absent entirely. Confirmed by:
- `acquisition.py` contains no session, holiday, weekend or DST logic;
- `\bdst\b` has **zero occurrences** in `src`;
- no `trading session` / `market session` terms exist anywhere.

The only "session" in the codebase is `session.py:154` — *"An in-memory
paper-trading session backed by one `PaperBroker`"*, i.e. a trading session, not a
market session.

**This is the single largest engineering gap**, and it blocks all forex work.

### 3.5 Gap classification

`acquisition` reports `missing_hours` for crypto and treats any as a blocking
issue. That is correct for 24×7 markets and **wrong for forex**, where a weekend
closure would be flagged as data corruption.

**Missing:** a market-aware classifier separating `legitimate_closure` from
`anomaly`.

### 3.6 Consuming the overlap guard

`normalize_source` hard-codes `RESEARCH_FIRST = 2024-01-01` and
`RESEARCH_LAST = 2025-12-31` (`acquisition.py:54-55`) and checks only that window.
It does **not** consult the registry's `consumed_windows`, which Phase 36
specifies as the authoritative anti-reuse record.

**Risk:** the strongest anti-reuse control in the design is documentation, not
code. The spent BTC holdout's protection rests on a recorded sentence in
`phase30/SUMMARY.md`, not on an enforced guard.

**Missing:** a registry-driven overlap check that refuses data intersecting any
recorded consumed window.

### 3.7 Automating independent re-derivation

Phase 34 re-derived all 24,288 ETH rows with independent code and found zero
mismatches. That is the strongest single piece of evidence in the whole data
chain — and it was **done by hand, twice, and is not automated.**

**Missing:** a reproducible re-derivation command that any reviewer can run.

### 3.8 Asset/dataset mismatch

`StrategyConfig.asset` is a label. The only non-declaration use is
`replay.py:363`, which passes it into the replay context. **Nothing validates
that a dataset matches its declared asset.**

Combined with the strategy being fully scale-invariant, this means an
unapproved or mislabelled run would proceed silently.

**Missing:** a loader-level assertion, or at minimum a registry cross-check.

---

## 4. Evidence required per governance stage

Restating Phase 36 §2 with the specific evidence this project can actually produce.

### DISCOVERED

| Evidence | Available? |
|---|---|
| Registry record with every field populated or explicitly `unknown` | **No registry exists** |
| Market type, venue, source pattern recorded | Manual only |
| Licence and attribution identified | Manual only (Phase 33 did this) |

### DATA CHECKED

| Evidence | Available? |
|---|---|
| C1–C14 all satisfied | **Only 5 of 14** |
| Every gap classified | No — gap classification absent |
| Volume semantics declared | **No** |
| Interval spacing verified | Yes, via acquisition |
| Independent recomputation | **Performed manually for ETH**, not automated |

### PROVENANCE VERIFIED

| Evidence | Available? |
|---|---|
| Grade A: publisher digest matched before parsing | **Yes** — proven 41/41 for ETH, 9/9 for BTC |
| Grade B: local digest only, limitation stated | **Yes** — ECB dataset, correctly labelled |
| Licence, attribution, redistribution recorded | Yes, in manifests |
| Per-archive provenance sidecars | Yes — 41 for ETH, corrected in Phase 35 |

**This is the strongest stage in the current system.**

### RESEARCH APPROVED

| Evidence | Available? |
|---|---|
| Data contract satisfied | **No** |
| Grade A or disclosed Grade B | Yes for ETH |
| **Untouched evaluation data reserved** | ETH 2026 exists but is **not reserved**; BTC has none; FX has none |
| Zero overlap with consumed windows | Not enforced by code |
| Preregistration naming the exact digest | **None exists** |
| Scope explicitly in bounds | **No** — cross-asset recorded NOT ESTABLISHED |

**No instrument can pass this stage today.**

### EVALUATED

| Evidence | Available? |
|---|---|
| Preregistration frozen before running | Precedent exists (`phase29/`) |
| Single run, results reported whatever they say | Precedent exists |
| Dataset digest named and re-verified at run time | Mechanism exists |

### MONITORED

| Evidence | Available? |
|---|---|
| Trigger definitions for returning to DATA CHECKED | Specified, not implemented |
| `RETIRED` reachable, deletion impossible | Not implemented |
| Drift detection | Does not exist |

---

## 5. Priority ordering of gaps

| Rank | Gap | Blocks |
|---|---|---|
| **1** | `consumed_windows` not enforced in code | **Anti-reuse protection for every instrument** |
| **2** | No session/holiday/DST library | All forex work |
| **3** | Volume semantics undeclared | Any cross-venue comparison; FX specifically |
| **4** | Preregistration mechanism not codified | Every evaluation |
| **5** | Independent re-derivation not automated | Repeatable provenance evidence |
| **6** | Price positivity and finiteness on the native load path | Robustness |
| **7** | Gap classification not market-aware | FX correctness |
| **8** | Asset/dataset mismatch unchecked | Silent mislabelled runs |
| **9** | No instrument registry | Everything above needs somewhere to live |
| **10** | Monitoring / drift detection absent | Long-run integrity |

---

## 6. Integrity approval remains separate from research approval

**This must survive every implementation choice in the table above.**

Passing every gap in §3 would make a dataset *integrity-complete*. It would
still **not** authorise evaluation. `RESEARCH APPROVED` additionally requires:
a preregistered question, reserved untouched data, confirmed scope, and a formal
governance record.

The strongest temptation this document creates is to treat "all gaps closed" as
"ready to evaluate". It is not. **Integrity completeness is a necessary
precondition, never a sufficient one.**

---

## 7. Not implemented in this phase

Per instruction, this phase documented gaps only. Nothing in §3 was implemented,
and no existing validator was modified.

---

## 8. Limitations

| # | Limitation |
|---|---|
| L1 | Gaps were identified by reading code, not by fuzzing or adversarial test |
| L2 | No test was written or run to confirm each gap is genuinely exploitable — only that the check is absent from the code |
| L3 | `walkforward.validate_dataset_integrity` was assessed by reading; its constants are tied to the frozen 2024–2025 dataset, so its applicability to ETH or FX is unclear and untested |
| L4 | The absence of session/DST logic was verified by search; a dynamic path elsewhere cannot be fully excluded, though `acquisition.py` and `dataset.py` were read directly |
| L5 | No performance figure was produced, so it is unknown whether these gaps would have changed any past result |