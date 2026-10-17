# Phase 61 — B5: Minimum Trade Count Methodology Brief

**Status: `OWNER DECISION REQUIRED` — threshold UNSET.**
No numeric value is proposed. No threshold was calculated from the reserved
period, and no performance figure from ETH 2026 exists or was inspected.

---

## 1. Intended research question

*Does a strategy configuration developed on BTC/USDT 2024–2025 transfer to
ETH/USDT 2026, after costs?*

The sample-adequacy rule exists to answer: *"is this window large enough for the
observed result to mean anything?"* — not to manufacture a result.

---

## 2. Verified evidence available now

| Fact | Source | Path |
|---|---|---|
| BTC holdout: **20 trades** from 912 bars | Phase 30 | `experiments/phase30/RESULTS_holdout.json` |
| Trades are **mechanically clustered, not independent** | Phase 30 recorded statement | `experiments/phase30/SUMMARY.md` |
| Verdict `INCONCLUSIVE`; net PF 0.4925; median net/trade −1.4220 | Phase 30 | same |
| ETH evaluation window: **6,744 bars** | reservation | `data/research_registry.json` |
| ETH warm-up: 17,544 bars (idx 0–17543), evaluation idx 17544–24287 | reservation | same |
| **ETH trade count** | **DOES NOT EXIST — not computed, not inspectable** | — |

---

## 3. Considerations

### 3.1 Dependence between trades

**[V]** Phase 30 recorded that BTC trades are **mechanically clustered**. A
breakout strategy entering on the same regime signal produces runs of trades
whose outcomes are correlated.

**Consequence: a raw trade count is not a count of independent observations.**
A rule that reads `N trades = N independent samples` will overstate the
information in the data. This is why an absolute floor alone is insufficient —
it must be paired with a registered caveat.

### 3.2 Statistical uncertainty

With clustered, serially dependent observations, the **effective sample size is
smaller than the trade count**. An adequacy rule expressed purely in trades
cannot express this. The registered caveat carries that limitation explicitly;
B6's interval width carries it quantitatively.

### 3.3 Market and strategy differences

| Difference | Direction |
|---|---|
| ETH vs BTC volatility | Likely more volatile → more signals, wider outcome dispersion |
| ETH liquidity vs BTC | Likely thinner; gaps and slippage behave differently |
| Both holdouts were **negative** | Prior expectation of an edge is **not** positive |

**No ETH trade count is known**, so the floor cannot be calibrated from the
target market. Deriving it from BTC would import BTC's trade frequency as if it
were an ETH requirement — acceptable as a *pre-registered estimate*, not as a
fact.

### 3.4 Multiple testing and prior exploration

**[V]** This configuration has been through BTC 2024–2025 development **and** a
BTC holdout. The holdout is spent (`consumed_windows`) and cannot be reused.

The evaluation is a **single registered comparison**, so no multiple-comparison
correction applies — but the **prior exploration** is real prior work and must be
disclosed, not treated as absent.

### 3.5 Why a small sample may be genuinely inconclusive

With 6,744 bars and clustered trades, the honest outcome may well be
`INCONCLUSIVE`. **That is a finding, not a failure.** A two-branch rule that
forces `INCONCLUSIVE` into "fail" would misrepresent the evidence — and the BTC
holdout produced exactly that outcome.

---

## 4. Transparent decision framework

**[R] Four framings exist in the project record** (`phase55/OWNER_DECISION_GATE.md`):

| # | Framing | Consequence |
|---|---|---|
| 1 | No minimum; report whatever trades occur | Any outcome interpretable, however thin; highest false-signal risk |
| 2 | Absolute floor at a chosen count | Simple; ignores clustering |
| 3 | **Floor plus a registered clustering caveat** | Gates the obvious case; prevents over-reading the remainder |
| 4 | No count floor; the interval determines adequacy | Most conservative; `INCONCLUSIVE` near-certain |

**Recommended structure: option 3**, paired with option 4's principle that the
interval governs adequacy. **The structure is a recommendation; the number is
not.**

### Two construction routes for the value

| Route | Method | Caution |
|---|---|---|
| **R1 — from fixed quantities** | Reserved bar count × a rate-per-bar estimate from **BTC development data** (2024–2025 only) | BTC frequency is an estimate, not an ETH fact |
| **R2 — direct judgement** | A number the owner considers the floor for meaningful inference | Expresses risk tolerance; not derivable from data |

**Route R1 is preferable** because it makes the floor a function of quantities
fixed *before* evaluation, rather than of anything observed in ETH 2026.

**Absolute constraint, either route:** the value **must not** be chosen or
adjusted after seeing the ETH trade count.

---

## 5. What is deliberately left unset

| Field | State |
|---|---|
| Minimum trade count | **OPEN — OWNER DECISION REQUIRED** |
| Derivation method (R1 or R2) | **OPEN — OWNER DECISION REQUIRED** |
| Adequacy framing (1–4) | **OPEN — OWNER DECISION REQUIRED** |
| Consequence below the floor | **Recommended: `INCONCLUSIVE`**, not `NOT SUPPORTED` |

**No threshold is proposed here, and none can be derived from existing records.**

---

## 6. Exact owner decision required

> **"Minimum trade count = [N]. Derived by [R1 — reserved bars × BTC development
> rate-per-bar / R2 — owner judgement]. Adequacy framing = [1/2/3/4]. Below N the
> verdict is `INCONCLUSIVE` regardless of sign. Registered clustering caveat
> accepted: [yes/no]."**

**Timing constraint:** this must be closed **before** the ETH trade count is
known, or the value is outcome-dependent.

**Not to be done by OpenCode:** setting the number, computing it from any ETH
figure, or inspecting reserved-period outcomes.