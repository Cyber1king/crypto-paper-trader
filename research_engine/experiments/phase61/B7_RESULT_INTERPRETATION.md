# Phase 61 — B7: Result Interpretation Framework

**Status: `OWNER DECISION REQUIRED` — the decision bar is UNSET.**
No numeric threshold is proposed. **No strategy is claimed to be profitable or
to have a demonstrated edge.**

---

## 1. Verified prior results — stated as recorded, not as expectation

| Window | Result | Path |
|---|---|---|
| BTC 2024–2025 (development) | Non-distinguishable from zero | Phase 9/10 records |
| BTC holdout, 912 bars | 20 trades · net PF **0.4925** · win rate recorded · max DD recorded · verdict **`INCONCLUSIVE`** · median net/trade **−1.4220** | `experiments/phase30/RESULTS_holdout.json` |
| BTC OOS 2026-01…2026-08 | baseline +0.05% PF 1.0424; A2 +0.14% PF 1.1330 — **"neither result is statistically distinguishable from zero"** | `data/oos/README.md` |

**Every prior period was non-distinguishable from zero.** The registered
hypothesis in the Phase 56/58 draft is therefore **H₀: no transferable edge** —
the *expectation*, not a fallback.

---

## 2. Proposed three-verdict framework

| Verdict | Condition | Meaning |
|---|---|---|
| **Promising** | Point estimate **and** interval both clear the pre-set bar, **and** sample adequacy met | Worth follow-up. **Not** evidence of a profitable strategy |
| **Inconclusive** | Sample adequacy not met, **or** the interval spans the bar | The study could not answer the question |
| **Against the hypothesis** | Estimate fails the bar with an adequate sample | The registered hypothesis is not supported |

**Three branches, not two.** A two-branch rule would classify the BTC holdout's
actual `INCONCLUSIVE` as failure and misrepresent the evidence.

**`INCONCLUSIVE` is a legitimate, expected outcome** for a clustered 6,744-bar
sample and must not be suppressed.

---

## 3. Factors the framework must account for

### 3.1 Transaction costs and slippage

**[V]** Frozen costs: `fee_rate = 0.001`, `slippage_rate = 0.0005`,
**`spread_rate = 0.0`**, `cost_deduction`, balance 10 000.0, risk fraction 0.01.
`bid_ask_available: false` — no bid/ask data was ever acquired.

**The zero-spread assumption biases results in favour of the strategy.** A
strategy whose edge is comparable to realistic spread would be eliminated by real
costs yet could appear viable here.

**Requirement:** any `Promising` verdict **must** state that real bid–ask costs
are unmodelled and that the bias runs against the strategy's favour.

### 3.2 Sample size and uncertainty

Handled by B5 (adequacy) and B6 (interval). **[V]** Trades are clustered, so
effective sample < trade count.

### 3.3 Drawdown and risk

Recorded metrics include max drawdown. **[V]** Prior BTC OOS max DD was recorded
as small (0.31–0.34%). Risk metrics must be **reported alongside** return metrics;
a good return with unacceptable drawdown is not a favourable result.

**No risk threshold is proposed** — none exists in the project record.

### 3.4 Profit factor and net performance

**[V]** Both are engine-computed and both are **imperfect**:
- Profit factor is unstable with few trades and **ignores trade ordering**.
- Net profit is dominated by a small number of large outcomes.

**Neither may be the sole criterion.** The registered primary metric is **net
expectancy per trade after costs**, because it is the quantity the interval
actually characterises.

### 3.5 Multiple testing and strategy selection

**[V]** One registered comparison, so no multiple-comparison correction applies.

**But:** the configuration passed through BTC development **and** a BTC holdout.
That prior exploration is real and **must be disclosed**, not treated as absent.
Disclosed degrees of freedom are listed in the Phase 56/58/59 preregistration
draft §8.

**No significance level is claimed.** This is a preregistered single comparison
with a pre-set rule, not a hypothesis test with an α. Reporting a p-value would
misrepresent the design.

### 3.6 Robustness and reproducibility

Report alongside the verdict: window, warm-up split, exact config hash and cost
hash, trade count, clustering caveat, zero-spread limitation, single-window
limitation, and any disclosed degree of freedom.

---

## 4. Evidence that would constitute each verdict

| Verdict | Would look like |
|---|---|
| **Promising** | Adequate sample; estimate above the bar; interval entirely above the bar; drawdown within a stated tolerance; all disclosed limitations restated |
| **Inconclusive** | Trade count below the floor, **or** interval spans the bar, **or** too few bootstrap blocks for a stable interval |
| **Against the hypothesis** | Adequate sample; estimate at or below zero after costs, with the interval not excluding zero in its favour |

**A narrow interval that spans the bar is `Inconclusive`, not
`Against the hypothesis`.** That distinction is the framework's purpose.

---

## 5. What no verdict may establish

- **Guaranteed or expected future profitability.**
- Generalisation beyond this single window.
- Suitability for live trading.
- Performance in other assets or regimes.
- That `Promising` implies a working strategy — it implies **one observation
  worth investigating**.

**A promising historical result would not guarantee future profitability.** This
must be stated in any report produced under this framework.

---

## 6. Fields left unset

| Field | State |
|---|---|
| Verdict structure | **Recommended: three branches** — confirmation open |
| `Promising` condition (estimate AND interval clear) | **OPEN — OWNER DECISION REQUIRED** |
| **The decision bar [value]** | **OPEN — OWNER DECISION REQUIRED** |
| Confidence level | **OPEN — see B6 #4** |
| Risk tolerance for drawdown | **No project record exists** — UNRESOLVED |

**No threshold is proposed, and none was derived from prior results.**

---

## 7. Exact owner decision required

> **"Adopt the three-verdict framework (Promising / Inconclusive / Against the
> hypothesis). `Promising` requires [estimate AND interval clear [bar]] with
> sample adequacy met. Confidence level [N]%, fixed jointly with B6. Any Promising
> report must state that spread costs are unmodelled and that the bias favours
> the strategy, and must not claim guaranteed profitability."**

**Timing constraint:** the bar must be fixed **before** any result is seen.

**Not to be done by OpenCode:** setting the bar, or characterising any strategy
as profitable.