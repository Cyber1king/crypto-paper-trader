# Phase 56 — Preregistration Draft

> **STATUS: DRAFT. NOT FROZEN. NO PREREGISTRATION ID ASSIGNED OR RESERVED.**
> **NO EVALUATION IS AUTHORISED.**
>
> Every unresolved owner decision is marked **`OPEN — OWNER DECISION REQUIRED`**.
> No performance figure from the reserved window appears here; none has been
> computed.
>
> Supersedes the Phase 55 draft in structure and detail. The Phase 55 document is
> preserved unchanged as a historical record.

---

## 0. Identification

| Field | Value |
|---|---|
| Preregistration ID | **`OPEN — NOT ASSIGNED. NOT RESERVED.`** |
| Draft status | Unfrozen, unapproved |
| Reserved window | `ETH-2026-RESERVATION` |
| Preregistration template source | `phase55/PREREGISTRATION_DRAFT.md` (preserved) |

---

## 1. Research question and falsifiable hypothesis

**Question.** Does a strategy configuration developed on BTC/USDT 2024–2025
transfer to ETH/USDT 2026, after trading costs?

**Falsifiable hypothesis.**

> **H₀:** Under this configuration, ETH/USDT net expectancy per trade after costs
> is **indistinguishable from zero** on the reserved window.
>
> **H₁:** Net expectancy per trade is sufficiently positive, and its uncertainty
> interval sufficiently clear of zero, to meet the pre-set bar (§7).

**H₀ is the stated expectation**, registered as the prior — not as a fallback.
Every prior period was non-distinguishable from zero (BTC 2024–2025; BTC holdout
`INCONCLUSIVE`, net PF 0.4925, median net/trade −1.4220, 20 trades / 912 bars).
A hypothesis predicting success would bias the study toward reporting success.

**Falsifiability.** H₁ is falsified if the estimate fails the bar with an
adequate sample, **or** if the interval spans the bar. Either ends the study for
this configuration. No variant may be substituted afterwards.

**Out of scope.** Any claim about ETH generally, other assets, live trading, or
regimes outside the reserved window.

---

## 2. Strategy configuration and provenance

All values read from source; unchanged from the frozen configuration.

| Field | Value |
|---|---|
| `asset` | `"BTC/USDT"` — a **label only**; the engine never checked it |
| `timeframe` | `"1h"` |
| `lookback` | `20` |
| `fast_period` | `5` |
| `slow_period` | `12` |
| `breakout_buffer` | `0.001` |
| `retest_tolerance` | `0.002` |
| `min_breakout_distance` | `0.0` |
| `trend_strength_min` | `0.001` |
| `retest_use_close` | `False` |
| `breakout_confirm_bars` | `1` |
| `max_holding_bars` | `None` |
| `stop_loss_pct` | `None` |
| `take_profit_pct` | `None` |
| `allowed_sides` | **`None` — both long and short** |

**Provenance.** Origin `walkforward.baseline_config()`. **Fitted parameters:
none** — this is a transfer test, not a fitted model, which constrains what §9
may claim.

**`config_hash`:** `OPEN — RECORD AT FREEZE`

---

## 3. Dataset fingerprint and evaluation window

| Item | Value |
|---|---|
| Dataset | `data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` |
| SHA-256 | `7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb` |
| Total bars | 24,288 |
| Warm-up | indices **0…17,543** — 17,544 bars, 2024-01-01 → 2025-12-31 |
| **Evaluation** | indices **17,544…24,287** — **6,744 bars**, 2026-01-01 → 2026-10-08 |
| Spacing | 1h / 3600 s |

**`dataset_fingerprint`:** `OPEN — RECORD AT FREEZE`

**Reservation controls**

| Control | Mechanism |
|---|---|
| Identity | SHA-256, not path — a copy cannot evade it |
| Range | `evaluation_first`/`last` must match the reservation |
| Explicit range | `run_backtest` raises without `evaluation_start` |
| Warm-up | Bars 0…17,543 produce no trades |
| Single use | `consume_reservation()`; duplicate consumption refused (Phase 55) |
| Concurrency | Inter-process lock on the registry read-modify-write (Phase 56) |
| Fail-closed | Writable `registry_file` required; empty registry refused |
| BTC holdout | Prohibited — recorded in `consumed_windows` |

---

## 4. Cost and execution assumptions

| Cost | Value |
|---|---|
| `fee_rate` | `0.001` |
| `slippage_rate` | `0.0005` |
| **`spread_rate`** | **`0.0`** — assumption |
| `execution_model` | `cost_deduction` |
| Balance / risk | `10000.0` / `0.01` |

> **Registered limitation.** Costs **exclude** bid–ask spread
> (`bid_ask_available: false`). Results therefore **overstate** achievable
> returns by an unquantified amount. **The bias runs in favour of the strategy.**
> This is the single largest threat to interpreting a positive result.

**Execution**

| Assumption | Value |
|---|---|
| Signals | Closed candles only |
| Fill | **Next bar open** |
| Intrabar fills | Never assumed |
| Reversal | Close, then re-enter at next open |
| End of window | `end_of_data` close |
| Stop / target / max holding | Disabled |

**Limitations.** Next-open fills are mildly optimistic; **gap risk is not
modelled**. Disabled optional exits mean this evaluates the **raw signal**.

**`costs_hash`:** `OPEN — RECORD AT FREEZE`

---

## 5. Minimum sample requirements

| Requirement | Value |
|---|---|
| Minimum bars | **6,744** — fixed by the reservation |
| **Minimum trade count** | **`OPEN — OWNER DECISION REQUIRED`** |
| Adequacy rule | **`OPEN — OWNER DECISION REQUIRED`** |

> **Registered caveat.** Trade count is not a count of independent observations.
> Phase 30 recorded that BTC trades are mechanically clustered.

**Below the minimum, the verdict is `INCONCLUSIVE` regardless of sign.**

---

## 6. Metrics and uncertainty methodology

| Role | Metric |
|---|---|
| **Primary** | Net expectancy per trade, after costs |
| Secondary | Win rate, net P&L, profit factor, max drawdown, trade count |

| Uncertainty | Value |
|---|---|
| Primary method | **Block bootstrap over time-ordered blocks** |
| Also reported | Per-trade 95% CI — **for continuity with Phase 30 only**, assumption-violating |
| Block length | **`OPEN — OWNER DECISION REQUIRED`** |
| Iterations | **`OPEN — OWNER DECISION REQUIRED`** |
| Basis | **`OPEN — OWNER DECISION REQUIRED`** |
| Confidence level | **`OPEN — OWNER DECISION REQUIRED`** |

**Constraint.** The basis **must not** use the reserved ETH window. Legitimate
bases: typical holding horizon; a fixed choice justified in advance; BTC
development-period autocorrelation (2024–2025 only).

---

## 7. Result interpretation and stopping rules

| Verdict | Condition |
|---|---|
| **Potentially useful** | Estimate **and** interval both clear the bar, sample adequacy met |
| **Inconclusive** | Adequacy not met, **or** interval spans the bar |
| **Against the hypothesis** | Estimate fails the bar with adequate sample |

**Bar:** `OPEN — OWNER DECISION REQUIRED`
**Confidence level:** `OPEN — OWNER DECISION REQUIRED`

**Three branches, not two** — the BTC holdout produced `INCONCLUSIVE`, which a
two-branch rule would misreport as failure.

**Stopping rules**

1. **One evaluation.** Consumed once; no second run under any configuration.
2. **Consume before interpreting.** `consume_reservation()` immediately after the
   run, before any result is read.
3. **No threshold substitution.** If the rule proves unsuitable, report it as
   unsuitable.
4. **No variant rescue.** A modified configuration requires a new preregistration
   and reservation.
5. **Publish failures.** `NOT SUPPORTED` is publishable.

**No verdict may assert** guaranteed profitability, generalisation beyond this
window, live-trading suitability, or performance in other assets.

---

## 8. Multiple-testing limitations

One registered primary comparison; no correction applied.

| # | Disclosed degree of freedom | Mitigation |
|---|---|---|
| 1 | Variant selection precluded by registration | §7 rule 4 |
| 2 | `allowed_sides = None` is one of several configurations | Fixed in §2 |
| 3 | Window end fixed by the reservation, not chosen | §3 |
| 4 | Zero-spread assumption flatters results | §4 |
| 5 | Single window, single regime — no sub-period robustness | §9 |
| 6 | Clustering reduces effective sample below trade count | §5 |
| 7 | A positive verdict still does not generalise | §9 |

**No significance level is claimed.** This is a preregistered single comparison
with a pre-set rule, not a hypothesis test with an α.

---

## 9. Reservation-consumption procedure

```
1. assert_clean_working_tree()                  -> must pass
2. Load the dataset; verify SHA-256             -> must match §3
3. run_backtest(candles, config, costs,
                research_context=ResearchContext(
                    dataset_sha256=..., instrument_id="ETH/USDT",
                    evaluation_first=2026-01-01T00:00:00,
                    evaluation_last =2026-10-08T23:00:00,
                    preregistration_id=<ID>,
                    config_asset="BTC/USDT",
                    cross_asset=<approved record>),
                evaluation_start=17544)
4. Guard decision recorded BEFORE any result is read.
5. consume_reservation("ETH-2026-RESERVATION",
                       registry_file=<path>,
                       preregistration_id=<ID>)   -> IMMEDIATELY
6. Only then interpret results.
```

**Ordering is the control.** Consuming at step 5, before step 6, makes
re-evaluation impossible even when a result disappoints — precisely the moment
the temptation arises.

**[V] Registered procedural limit.** `run_backtest` does **not** auto-consume.
Consumption is a separate explicit call. A proposal to add a
`consume_on_completion` field is documented in
`phase56/RESERVATION_HARDENING.md` §3.3 and **awaits owner approval**.

---

## 10. Approval and authorization gates

| Gate | Requirement | Status |
|---|---|---|
| B1 | Python package licence | `OPEN — OWNER DECISION REQUIRED` |
| B2 | ECB registry correction | Ready for approval |
| B3 | Binance `licence_knowledge` | Ready for approval |
| B4 | ECB provenance | `OPEN` |
| **B5** | Minimum trade count | **`OPEN — OWNER DECISION REQUIRED`** |
| **B6** | Block length, iterations, basis, level | **`OPEN — OWNER DECISION REQUIRED`** |
| **B7** | Decision rule and bar | **`OPEN — OWNER DECISION REQUIRED`** |
| **B8** | Cross-asset approver and date | **`OPEN — OWNER DECISION REQUIRED`** |
| **B9** | Confirm Option A | `OPEN` |
| **B10** | Freeze and assign ID | `OPEN` — blocked on B5–B8, B11 |
| **B11** | Evaluation authorisation | **CLOSED** |

**Cross-asset authorization record**

| Field | Value |
|---|---|
| `config_asset` | `"BTC/USDT"` |
| `dataset_instrument` | `"ETH/USDT"` |
| `justification` | Testing whether an unchanged BTC-derived configuration transfers to ETH — not a tuning opportunity |
| `approver` | **`OPEN — OWNER DECISION REQUIRED`** |
| `date` | **`OPEN — OWNER DECISION REQUIRED`** |

---

## 11. Freeze checklist

- [ ] B5, B6, B7 closed with values recorded
- [ ] B8 approver and date recorded
- [ ] B9 confirmed (Option A)
- [ ] Preregistration ID assigned
- [ ] `config_hash` recorded
- [ ] `costs_hash` recorded
- [ ] `dataset_fingerprint` recorded
- [ ] Evaluation window and warm-up split confirmed against the reservation
- [ ] `CrossAssetAuthorization` validated by `from_record()`
- [ ] `assert_clean_working_tree()` passes
- [ ] Reservation updated with the preregistration ID
- [ ] **B11 authorisation obtained (separate, explicit)**

**Until every box is ticked: reservation remains `RESERVED` / `used: false` /
`preregistration_id: null`, and no evaluation may run.**

---

**Not frozen. No ID assigned. No evaluation authorised.**