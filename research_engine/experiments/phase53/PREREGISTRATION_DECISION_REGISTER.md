# Phase 53 — Preregistration Decision Register

**Date:** 2026-10-09
**Covers:** the eight open decisions from `phase51/DECISIONS_REQUIRING_APPROVAL.md`

**No threshold values are proposed in this register.** Numeric profitability
criteria require an owner's risk appetite, not a researcher's guess, and any
number chosen here would become a number that can be adjusted later. Fields
marked `[OWNER]` must be filled by a human before the preregistration can be
frozen.

**No decision below is made.** This register records evidence, proposes
structure, and identifies who must approve. Phase 53 recommends **Option A** for
the evaluation design (`ETH_EVALUATION_DESIGN.md` §6); that recommendation is
itself subject to D-7.

---

## D-1 — Minimum-trade requirement and sample adequacy

**Existing evidence**

| Fact | Source |
|---|---|
| BTC holdout: 912 bars → **20 trades** | `phase30/RESULTS_holdout.json` |
| Trades are **mechanically clustered, not independent** | Phase 30 recorded statement |
| Verdict `INCONCLUSIVE`; median net/trade **−1.4220** | Phase 30 |
| ETH evaluation window: **6,744 bars** (7.4× the BTC holdout) | reservation entry |
| No ETH trade count exists — **not computed, not inspectable** | reservation is `RESERVED` |

**Proposed decision (structure, not value)**

Do **not** set a raw trade-count threshold. Trade count is a poor adequacy proxy
here because the clustering above breaks the independence assumption any
count-based test relies on. Record instead:

1. A **minimum trade count** `[OWNER]` — a floor below which the result is
   declared uninformative regardless of its sign.
2. An **effective-sample caveat** stated in the preregistration itself, so no
   later reader treats 20 trades as 20 independent observations.
3. A **clustering-robust or block-bootstrap uncertainty method** — see D-2.

**Decidable before evaluation?** Yes, entirely. It depends on expected trade
frequency, which can be reasoned about from bar count — but the *value* must be
set by a human, not back-derived once trades are seen.

**Human approval required?** **Yes** — `[OWNER]`.

> Rationale for resisting a "natural" number: any trade threshold chosen after
> seeing an ETH trade count is chosen with knowledge of the result. That is the
> failure mode this whole protocol exists to prevent.

---

## D-2 — Uncertainty reporting

**Existing evidence.** Phase 30 used a **per-trade 95% confidence interval of the
mean**, which the data-quality note flags as optimistic given clustering. BTC
holdout: CI spans zero, pre- and post-costs.

**Proposed decision**

Adopt **block bootstrap over time-ordered blocks** as the primary uncertainty
method, with the per-trade CI reported alongside for continuity. Blocks respect
serial dependence; per-trade intervals do not.

Block length and iteration count: `[OWNER]`. Report both the point estimate and
the interval, and state explicitly whether the interval crosses zero.

**Decidable before evaluation?** Yes. Block length must be chosen without
reference to outcome — a defensible default is tied to the strategy's holding
horizon rather than to observed results.

**Human approval required?** **Yes** for the parameters; **no** for the choice of
block bootstrap over per-trade CI, which is a method decision with a sound
rationale.

---

## D-3 — Decision rule

**Existing evidence.** No profitability threshold has ever been established in
this project. BTC 2024–2025 and the BTC holdout were both non-distinguishable
from zero. There is **no prior performance claim** to anchor a rule to.

**Proposed decision**

Adopt a rule with **three outcomes**, not two:

| Outcome | Condition |
|---|---|
| `SUPPORTED` | Point estimate and interval both clear the pre-set bar `[OWNER]` |
| `NOT SUPPORTED` | Estimate fails the bar |
| `INCONCLUSIVE` | **Sample adequacy (D-1) not met**, or interval spans the bar |

The third branch is essential. With a clustered sample and a single window,
`INCONCLUSIVE` is a likely and legitimate outcome — the BTC holdout produced
exactly that. A two-branch rule would force `INCONCLUSIVE` into
`NOT SUPPORTED`, discarding the distinction the whole protocol maintains.

The bar value is `[OWNER]`. **No numeric threshold is proposed here.**

**Decidable before evaluation?** Yes — and it must be. A decision rule fixed
after seeing the result is not a rule.

**Human approval required?** **Yes** — `[OWNER]`.

---

## D-4 — Cross-asset authorization

**Existing evidence**

- `StrategyConfig.asset` is documented as **only a label**; the engine never
  checked it (`researchguard.py` L13–15).
- The frozen configuration declares `asset="BTC/USDT"`.
- `CrossAssetAuthorization` **already exists** (`researchguard.py` L122) with
  fields including `config_asset`, `dataset_instrument` and `justification`;
  `from_record()` **rejects** a record missing any of them.
- `ETH/USDT` `research_note` records that no cross-asset authorization exists.

**Proposed decision**

Authorize the transfer explicitly and in writing, using the existing dataclass
rather than a new mechanism. Required content:

- `config_asset`: `"BTC/USDT"`
- `dataset_instrument`: `"ETH/USDT"`
- `justification`: why an unchanged BTC-derived configuration is being applied
  to ETH — i.e. that this is a genuine transfer test, not a tuning opportunity
- **Named approver and date** `[OWNER]`

**Decidable before evaluation?** Yes, and it **must** be: the guard refuses to
run without it, so there is no ordering hazard.

**Human approval required?** **Yes** — named approver and date. This is the
decision that most needs a person: it asserts that BTC development carries over
to ETH, which is a research claim, not a code fact.

---

## D-5 — Zero-spread assumption

**Existing evidence**

- `TradingCosts.spread_rate = 0.0` is **frozen** in both `costs.py` and
  `phase13_costs()`, and is part of the frozen cost fingerprint.
- Registry: `bid_ask_available: false` — no bid/ask data was acquired.
- Binance Vision klines contain OHLCV only; there is no spread series.
- ETH is extremely liquid by general expectation, but **this phase found no
  authoritative, citable spread measurement** for the pair. That claim remains
  unsourced and is not treated as evidence here.

**Proposed decision**

Keep `spread_rate = 0.0`, unchanged, and state the limitation as a named
assumption in the preregistration: *costs exclude spread; results therefore
overstate achievable returns by an unquantified amount.*

Do **not** introduce a sensitivity band without a source for the spread. A
band with invented endpoints would be a fabricated parameter, and it would also
change the frozen cost fingerprint.

**Decidable before evaluation?** Yes.

**Human approval required?** **Yes** to accept the limitation explicitly. A
sourced band (e.g. from measured spread data) would need separate acquisition,
which is out of scope here.

---

## D-6 — Long-only versus both directions

**Existing evidence.** `StrategyConfig.allowed_sides = None`, meaning **both
directions are permitted**. This is part of the frozen configuration.

**Proposed decision**

Keep `allowed_sides = None` for the primary evaluation. Restricting to long-only
would be a **parameter change** made after the configuration was frozen and
after BTC results were observed — the definition of tuning, even if motivated by
purity rather than performance.

If a long-only variant is scientifically interesting, it is a **separate,
separately preregistered experiment** with its own ID and its own reserved data.
It is not a variant of this one.

**Decidable before evaluation?** Yes.

**Human approval required?** Recommendation is **no change**, so effectively no —
but a departure from the frozen configuration always requires approval.

---

## D-7 — Single window, or generalise `walk_forward` first

**Existing evidence**

- `walk_forward` is BTC-pinned at `DATASET_FIRST` / `DATASET_LAST`
  (`walkforward.py` L320–328); count and hash are already parameterised.
- `run_backtest` + `ResearchContext` is ETH-capable **today**.
- The strategy has **no fitted parameters**, so walk-forward would provide
  segmented evaluation, not train/test generalisation.
- Reserved ETH window: 6,744 bars — fragmentable but finite, consumed once.

**Proposed decision**

**Option A** — a single pre-registered ETH evaluation window. Rationale in
`ETH_EVALUATION_DESIGN.md` §6: zero engine change, no frozen-BTC risk, no
multiplicity hazard, and the reservation already describes exactly one run.

Option B remains the right long-term direction and is recommended as its own
later phase, on its own data — not on the reserved window.

**Decidable before evaluation?** Yes. This is an engineering-and-science
judgement available now.

**Human approval required?** **Yes** — it determines the preregistration's whole
structure.

---

## D-8 — Final approval to freeze and to evaluate

**Existing evidence**

- Reservation `ETH-2026-RESERVATION`: `status: RESERVED`, `used: false`,
  `preregistration_id: null`.
- Its own note: *"Declared intent only. **NOT protected against evaluation** until
  a preregistration is frozen and the guard is exercised."*
- `research_approval: DATA_VERIFIED_NOT_RESEARCH_APPROVED`.
- `researchguard.py` L27–28: there is deliberately **no** `skip_guard` flag on
  any function. No code-level bypass exists.

**Proposed decision**

Treat freeze and evaluate as **two separate approvals**, not one:

| Approval | Preconditions |
|---|---|
| **Freeze** | D-1…D-7 all closed with values recorded; preregistration content complete; named approver and date |
| **Evaluate** | Frozen preregistration with an assigned ID; recorded `CrossAssetAuthorization`; explicit authorisation to consume the reservation |

Freezing does not authorise running. Evaluation consumes the reservation
irreversibly — the guard permits exactly one use.

`RESERVED` is a marker, not a lock. The protection is real only once the guard
has been exercised, which requires the freeze to exist first.

**Decidable before evaluation?** Yes — and both must precede it.

**Human approval required?** **Yes**, explicitly, by name, for both.

---

## Summary

| ID | Decision | Can be closed pre-evaluation | Numeric input needed | Approver |
|---|---|---|---|---|
| D-1 | Minimum trades / adequacy | Yes | **Yes — `[OWNER]`** | Human |
| D-2 | Uncertainty method | Yes | Yes — block length `[OWNER]` | Human (params) |
| D-3 | Decision rule | Yes | **Yes — bar `[OWNER]`** | Human |
| D-4 | Cross-asset authorization | Yes — guard requires it | Named approver + date `[OWNER]` | Human |
| D-5 | Zero-spread limitation | Yes | Band only if sourced | Human |
| D-6 | Both directions (unchanged) | Yes | No | Human if changed |
| D-7 | Option A vs B | Yes | No | Human |
| D-8 | Freeze + evaluate | Yes — must precede evaluation | Named approver + date `[OWNER]` | Human |

**All eight remain OPEN.** None is closed by this phase, and no preregistration
ID has been assigned or reserved. Four require numeric inputs that only an owner
should supply.

**The sequencing constraint that matters:** every one of these is decidable
*before* evaluation, and three (D-1, D-3, D-7) only have meaning if closed
*before* evaluation. A decision left open until results exist has already been
decided by the results.