# Phase 51 — Decisions Requiring Approval

**Date:** 2026-10-09
**Status: NONE OF THESE DECISIONS HAS BEEN MADE.**

Eight decisions cannot be settled from existing evidence. Each is presented with
options, consequences and a rationale for the proposal — but the choice belongs
to a person, not to this document.

**No profitability threshold is proposed as a number.** Where an option would
require a figure, the figure is left blank and explained, because a threshold
chosen now still becomes the standard the data is judged against, and choosing
it to be attainable is not the same as choosing it to be correct.

---

## D-1 — Minimum-trade requirement and sample adequacy

**Why it cannot be decided here.** Phase 30 recorded, before its own results
were seen, that its 20 trades were *not independent*: one position at a time,
mean hold far exceeding the sample, mechanically clustered. A minimum count
justified by "independent observations" would therefore be unjustified.

**Relevant facts.** ETH evaluation window = 6,744 bars (≈281 days). BTC holdout
= 912 bars (≈38 days) producing 20 trades, verdict INCONCLUSIVE, median net per
trade −1.4220.

| Option | Rule | Consequence |
|---|---|---|
| **A** *(proposed)* | Fixed minimum trade count, stated before running | Simple and falsifiable, but counts clustered observations as if independent. Must be paired with a clustering caveat |
| **B** | Minimum **independent** trade episodes, defined by a stated non-overlap rule | Statistically honest, but requires defining independence — which needs observed hold durations this project does not have |
| **C** | No count rule; report count and treat adequacy qualitatively | Avoids a false precision, but makes "too few trades" a judgement call after the fact |
| **D** | Declare the window structurally incapable of supporting a conclusion | Defensible given clustering, and maximally conservative |

**Proposal: A with an explicit clustering caveat**, because a pre-declared
threshold is more falsifiable than a post-hoc judgement — but the threshold
value itself is **[blank]** and is the human decision.

**What this depends on:** D-7. If `walk_forward` is generalised first, more
windows exist and adequacy may be answerable differently.

---

## D-2 — Uncertainty reporting

**Why it cannot be decided here.** No statistical significance has been claimed
anywhere in this project; Phase 31 made that an explicit property. Selecting a
confidence level or test without observed data is precisely the post-hoc
rationalisation the process exists to prevent.

| Option | Approach | Consequence |
|---|---|---|
| **A** *(proposed)* | Report point estimates with explicit sample size and **no** significance claim; state that the window cannot support an inferential claim | Honest, consistent with Phase 31, and less informative |
| **B** | Pre-specify a bootstrap or permutation test and a confidence level | More informative, but the test choice and level are themselves choices made in advance of seeing data |
| **C** | Report both A and B, with B labelled exploratory | Maximum information; the risk is that B's output gets read as the conclusion |

**Proposal: A**, with B permitted only if its test and level are fixed here,
in writing, before any run.

**Blanks requiring approval under B:** test **[blank]**, confidence level
**[blank]**, minimum episode length for independence **[blank]**.

---

## D-3 — Decision rule

**What result means what.** The BTC precedent is `INCONCLUSIVE`, declared in
advance — a category this project has already used honestly.

| Outcome | Option A *(proposed)* | Option B |
|---|---|---|
| Strongly positive | Report as recorded; **no** claim of an edge | Claim evidence of an edge |
| Weakly positive | Report as recorded; explicitly inconclusive | Claim evidence of an edge |
| Negative | Report as recorded; closes the question for this configuration | Report as recorded |
| Mixed / ambiguous | `INCONCLUSIVE` | `INCONCLUSIVE` |

**Proposal: A** — the positive rows deliberately do **not** license an edge
claim, because one window, one run, on an asset whose correlation with BTC is
high, cannot establish one. Writing "evidence of an edge" into a rule before
seeing data makes the rule a promise rather than a test.

**Critical:** no numeric profitability threshold is proposed. Defining one here
— before any result — would still define what counts as success, and choosing it
to be attainable is not the same as choosing it to be correct. The blank is
intentional.

**Blanks requiring approval:** net-P&L threshold **[blank]**, net profit factor
threshold **[blank]**, maximum drawdown ceiling **[blank]** — *if* the approver
wants thresholds at all. Option A does not require them.

---

## D-4 — Cross-asset authorization

**Why it needs a person.** The frozen configuration declares
`asset="BTC/USDT"` and would be applied to ETH/USDT data. That is an instrument
transfer, and `CrossAssetAuthorization` exists to make it explicit and recorded.

**What must not happen:** editing the configuration to `asset="ETH/USDT"`. That
relabels the data rather than authorising the transfer, and destroys what is
being tested — whether a *BTC-derived* configuration transfers.

| Field | Value |
|---|---|
| `dataset_instrument` | `ETH/USDT` |
| `config_asset` | `BTC/USDT` |
| `justification` | tests transferability of a BTC-selected configuration |
| `approved_by` | **[blank — named individual required]** |
| `approved_on` | **[blank]** |

**This cannot be self-approved by whoever runs the evaluation.** That would make
the authorization a formality.

---

## D-5 — Zero-spread assumption for a liquid asset

**The fact.** `spread_rate = 0.0` because no bid/ask data was acquired for
either instrument; the registry records `bid_ask_available: false` for both.

**Why it is material for ETH specifically.** Phase 47 established that in a
liquid market a bid/ask spread is often comparable to the signal being traded,
so ignoring it risks inverting a result's meaning rather than merely weakening
it. ETH/USDT is among the most liquid pairs available. The 5 bps slippage
assumption partially absorbs the effect, but slippage and spread are not the same
quantity and the model does not claim they are.

| Option | Approach |
|---|---|
| **A** *(proposed)* | Keep 0.0 and disclose the limitation prominently in any report | 
| B | Report alongside a pre-specified sensitivity band, e.g. 1/2/5 bps | 
| C | Acquire bid/ask data and re-derive before running — **not possible**: the reserved window is historical hourly candles with no book data |

**Proposal: A**, optionally with B. Option C is unavailable and should not be
promised.

**Note the ordering constraint:** a sensitivity band must be **pre-specified
here**. Choosing it after seeing the headline number is curve-fitting, not
sensitivity analysis.

---

## D-6 — Long-only versus both directions

**The fact.** `allowed_sides = None` permits long and short. On spot ETH/USDT a
short is not directly expressible; it is a paper-only modelling convention that
the engine supports for BTC and would carry over to ETH.

| Option | Consequence |
|---|---|
| **A** *(proposed)* | Keep `allowed_sides = None`, matching the frozen BTC configuration exactly | 
| B | Set long-only, which is expressible on spot but **changes the configuration** |

**Proposal: A**, because B is a configuration change and §2 freezes the
configuration. B would be defensible on realism grounds, but it is a different
evaluation and must be declared as such — not slipped in as a realism fix.

---

## D-7 — Single window, or generalise `walk_forward` first

**The finding.** `walkforward.DATASET_PATH` and `DATASET_SHA256` are hard-wired
to the BTC primary dataset. Verified: `validate_dataset_integrity` raises
`WalkForwardValidationError` on the ETH series, with the BTC default path *and*
with the ETH path supplied — the expected bounds are constants.

**Consequence:** `run_backtest` with a `ResearchContext` is the **only**
ETH-capable path. Any walk-forward framing is unavailable today, and this
evaluation is therefore a **single-window** evaluation.

| Option | Consequence |
|---|---|
| **A** *(proposed)* | Accept a single-window evaluation and disclose the reduction in evidence | 
| B | Generalise `walk_forward`'s dataset binding first, then evaluate multiple windows |

**Proposal: A**, on the grounds that B is a code change which must be completed
and verified *before* the protocol is frozen, and would consume the reservation
across several windows — a materially different claim from the one proposed.

**If B is chosen:** the protocol is not frozen until the code change is merged
and tested, and the reservation must be re-specified to cover the windows
intended. That is a governance action, not a documentation fix.

---

## D-8 — Final approval to freeze and to evaluate

**Two distinct approvals, not one.** They are listed separately because
conflating them is how a frozen protocol becomes a permission slip.

| Approval | Meaning |
|---|---|
| **Freeze** | Fix the protocol text and assign `preregistration_id`. The registry still refuses evaluation until a preregistration is registered |
| **Evaluate** | Permit the single run |

**Nothing in this repository can do either.** The registry refuses evaluation
while `preregistration_id` is `null`, which is correct. Assigning an identifier
is a deliberate act that must follow D-1 … D-7.

**Approver(s): [blank]. Date: [blank].**

---

## Summary

| # | Decision | Status | Proposed | Needs |
|---|---|---|---|---|
| D-1 | Minimum trades / adequacy | **OPEN** | A + clustering caveat | Threshold value |
| D-2 | Uncertainty reporting | **OPEN** | A | — |
| D-3 | Decision rule | **OPEN** | A, no edge claim | Whether thresholds exist at all |
| D-4 | Cross-asset authorization | **OPEN** | — | Named approver + date |
| D-5 | Zero spread on a liquid pair | **OPEN** | A, optionally B | Band values if B |
| D-6 | Long-only vs both | **OPEN** | A (unchanged) | — |
| D-7 | Single window vs code change | **OPEN** | A | — |
| D-8 | Freeze / evaluate approval | **OPEN** | — | Named approver + date |

**Eight open. Zero made.** The ETH reservation correctly remains untouched.