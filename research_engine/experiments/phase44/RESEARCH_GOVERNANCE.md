# Phase 44 Research Governance

**Date:** 2026-10-09
**Status:** Consolidated. **No evaluation is approved by this document.**

This is the single place where the research rules live. It supersedes the
scattered statements in Phases 29–42 and records what remains undecided.

Nothing here was derived from ETH 2026 results, because none were computed.

---

## 1. The governing principle

**A window is spent by an evaluation, never by an attempt.**

Every other rule exists to protect that one. A crash, a failed guard, or a
curious glance must not consume data. Conversely, once an evaluation has run, the
window is gone regardless of whether the result was good, bad or inconclusive.

---

## 2. BTC holdout — permanently retired

| Field | Value |
|---|---|
| Dataset | `data/oos/binance_spot_BTCUSDT_1h_202609-202610.csv` |
| SHA-256 | `c475e541c9c8fb393713854e1640d3a2a029100472dc677e9fe11f3e42a8f99b` |
| Window | 2026-09-01 00:00 → 2026-10-08 23:00 UTC, 912 bars |
| Pre-registration | `phase29d-eth0-btc-holdout` (`b06f36e2…`) |
| Evaluated | Exactly once, Phase 30B |
| Result | **INCONCLUSIVE** — 20 trades, net P&L −12.322857, net PF 0.4925 |
| Registry state | `consumed_windows`, `outcome: INCONCLUSIVE` |

**Permanently retired.** It may be read as a historical record. It may never
validate, select, tune or compare anything.

This is the only untouched out-of-sample data this project has ever held, and it
returned a negative result. That fact is recorded because it is the most
informative thing available, not because it is discouraging.

The other two BTC windows — the primary 2024–2025 dataset (used across 12+
configuration searches) and the Phase 10/11 OOS window — are equally consumed.
**No untouched BTC data remains.**

---

## 3. ETH evaluation — reserved, not approved

| Field | Value |
|---|---|
| Dataset | `data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` |
| SHA-256 | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| Warm-up | 2024-01-01 → 2025-12-31, 17,544 bars — indicator context, **no trades** |
| Evaluation | 2026-01-01 → 2026-10-08, 6,744 bars, `evaluation_start_index = 17544` |
| Registry state | `status: RESERVED`, `used: false`, `preregistration_id: null` |
| Registry entry | `research_approval: DATA_VERIFIED_NOT_RESEARCH_APPROVED` |

**No ETH 2026 performance has been computed, inspected or revealed** in any of
Phases 39–45.

Enforcement was verified by live probe in Phase 42: all six strategy-executing
entry points refuse the reserved series without a valid research context, across
eight series shapes including arbitrary sub-slices, reversals and
every-other-bar subsets.

---

## 4. Unresolved preregistration decisions

These must be settled **before** any result is observed. Each is listed with why
it matters and what remains unknown. **None is invented here.**

### 4.1 Research question — UNRESOLVED

Phase 38 drafted a question; Phase 42 found it not finalised.

Open: what claim would ETH evidence test? The BTC-derived configuration was
tuned on BTC data. Transferring it to ETH tests *transferability*, which is a
narrower and more falsifiable claim than "this strategy works" — but the exact
wording is not settled, and the wording determines what counts as success.

**Risk if skipped:** a vague question makes every result interpretable, which is
the same as having no decision rule.

### 4.2 Configuration — UNRESOLVED

The frozen `StrategyConfig` was selected on the BTC primary dataset across 12+
searches. Whether ETH is evaluated with that exact configuration, or with a
re-derivation, is undecided.

Open: does ETH evaluate the *frozen BTC configuration* (testing transferability)
or a configuration selected on ETH warm-up data only (testing within-asset fit)?

These answer different questions. The first is more honest about the transfer
claim; the second risks selecting on data adjacent to the evaluation window.

**Current state:** `StrategyConfig.asset` remains `"BTC/USDT"`. It has **not**
been modified, and must not be, to make ETH data appear to be BTC.

### 4.3 Costs — PARTIALLY RESOLVED

Frozen costs exist (`phase13_costs`) and were used for the BTC holdout. Open:
whether those values are appropriate for ETH specifically, given different
venue depth and volatility.

**Known limitation carried forward:** no bid/ask data was acquired for either
instrument. Spread cannot be modelled. This is a stated limitation, not an
assumption of zero cost, and it applies equally to every result this project has
produced.

### 4.4 Execution assumptions — UNRESOLVED

Not documented for an ETH evaluation. Open: fee structure, slippage model,
whether funding applies (24×7 spot does not have perpetual funding), position
sizing, and how `evaluation_start` interacts with indicator warm-up.

### 4.5 Thresholds and decision rules — UNRESOLVED

**Deliberately not invented.** A threshold chosen after seeing a result is not a
threshold; it is a rationalisation. No number is proposed here.

Open: what result would count as evidence for transferability? What would count
against? Is a single 6,744-bar window sufficient, or is the sample too small to
distinguish an edge from noise? What is the null hypothesis, and what test?

Phase 31's BTC analysis suggests this project's single windows have been too
small to support confident conclusions — which is itself a reason to be careful
about claiming otherwise for ETH.

### 4.6 Uncertainty reporting — UNRESOLVED

Open: how will confidence intervals, sample-size limits, and the risk of a single
window overfitting be reported? A point estimate from 6,744 bars presented
without uncertainty would misrepresent what is known.

### 4.7 Stopping rules — UNRESOLVED

Open: what happens if the evaluation is inconclusive, as BTC's was? Is a second
window permitted (no — the reservation covers one), or is the question closed
until new untouched data exists?

---

## 5. Cross-asset authorization — explicit and auditable

Running a BTC-derived configuration against ETH data is permitted **only** with
an explicit `CrossAssetAuthorization` naming:

- `dataset_instrument`: the data's actual instrument
- `config_asset`: the configuration's label
- `justification`: why the transfer is legitimate
- `approved_by`: who authorised it
- `approved_on`: when

**Status: mechanism implemented and tested, no record created.** An
authorization for the BTC-config → ETH transfer does not exist yet, and must be
created and justified before any evaluation.

The authorization must match *this* pair exactly. Authorization granted for
SOL→ETH does not permit BTC→ETH.

---

## 6. Standing rules

| Rule | Enforcement |
|---|---|
| No evaluation without a valid research context | Guard refuses; verified at all 6 entry points |
| A consumed window is never reused | Registry records consumption; refuses outright |
| A reserved window is spent once, explicitly | `consume_reservation()` after a successful run |
| Omitting a context does not exempt a run | Series is fingerprinted independently |
| Instrument identity is enforced | `DatasetIdentity.assert_compatible_with_config` |
| Overlap status is always explicit | `checked` / `skipped` / `failed`, default `failed` |
| Forex stays blocked | No OHLC data, no session/DST validator |
| Data quality never implies approval | `RESEARCH_APPROVED` requires a preregistration id |

---

## 7. What may proceed now

**Permitted:** drafting the research question, the preregistration, thresholds,
and decision rules — as long as **no result is observed first**.

**Prohibited:**

- Running any backtest, replay, or walk-forward against ETH 2026.
- Reading ETH 2026 performance in any form.
- Reusing any consumed BTC window.
- Tuning parameters on ETH data.
- Modifying the frozen BTC configuration so ETH data appears to be BTC.
- Setting thresholds after seeing results.
- Converting ECB reference rates into synthetic OHLC.
- Inventing forex session or DST rules.

---

## 8. Honest statement

The safeguards are real and verified. They protect the reserved window from
accidental reuse, and they are implemented as code rather than prose.

They do not make the strategy profitable, and nothing in Phases 39–45 provides
evidence that it is. The single pre-registered out-of-sample test this project
has run returned a net profit factor of 0.4925 and was recorded as inconclusive.
No result since then changes that.