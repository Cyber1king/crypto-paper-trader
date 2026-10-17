# Phase 53 — ETH Evaluation Design

**Date:** 2026-10-09
**Question:** why is the walk-forward path BTC-pinned, can it be made
asset-agnostic without altering frozen BTC semantics, and which evaluation
design should ETH use?

**Recommendation: Option A for the reserved window now; Option B only as a
separately designed framework. Neither is implemented here, and neither may be
executed without explicit approval.**

---

## 1. Why the walk-forward path is BTC-pinned

`walkforward.py` binds the primary dataset at module level:

```python
L48  DATASET_PATH   = "data/BTCUSDT_1h_Cleaned (1).csv"
L51  DATASET_SHA256 = (...)
L55  DATASET_FIRST  = datetime(2024, 1, 1, 0, 0)
L56  DATASET_LAST   = datetime(2025, 12, 31, 23, 0)
L57  DATASET_CANDLES = 17_544
```

`validate_dataset_integrity()` (L283) then uses them unevenly:

```python
L283  def validate_dataset_integrity(
L284      candles,
L286      expected_sha256: str | None = DATASET_SHA256,   #  ← parameterised
L287      expected_count: int | None = DATASET_CANDLES,  #  ← parameterised
      ) -> None:

L320      if stamps[0] != DATASET_FIRST:                  #  ← BARE CONSTANT
L322          raise ...(f"dataset starts {stamps[0]}, expected {DATASET_FIRST}")

L325      if stamps[-1] != DATASET_LAST:                  #  ← BARE CONSTANT
L327          raise ...(f"dataset ends {stamps[-1]}, expected {DATASET_LAST}")

L330      if expected_count is not None and len(candles) != expected_count:   # ← overridable
L335      if path is not None and expected_sha256 is not None:                 # ← overridable
L338          if actual != expected_sha256:                                     # ← overridable
```

**The pinning is narrower than "the module is BTC-specific".** Count and hash are
already overridable parameters. Only the **timestamp bounds** are hard-wired,
and they are the sole reason ETH is rejected:

```
dataset ends 2026-10-08 23:00:00, expected 2025-12-31 23:00:00
```

The check fires before any engine loop runs, so no trades are generated and no
performance is computed — the guard fails closed at the data layer.

The rest of the walk-forward module is already **asset-neutral**: costs
(`FEE_RATE`, `SLIPPAGE_RATE`, `SPREAD_RATE`, `STARTING_BALANCE`, `RISK_FRACTION`),
`WARMUP_RULE = "full_preceding_series"`,
`BOUNDARY_POLICY = "retain_boundary_force_closes"`, `assert_no_state_carry()`,
`assert_clean_working_tree()`, and the window/window-id logic carry no BTC
assumption. `baseline_config()` and `a2_config()` set `asset="BTC/USDT"` — but
per `researchguard.py` L13–15, **`StrategyConfig.asset` is only a label**, and
the guard exists precisely because the engine never checked it.

---

## 2. Can an asset-agnostic design avoid altering frozen BTC semantics?

**Yes. The change is small and mechanically safe.** This is the significant
finding for §4.

```python
def validate_dataset_integrity(
    candles,
    path=None,
    expected_sha256: str | None = DATASET_SHA256,
    expected_count: int | None = DATASET_CANDLES,
    expected_first: datetime | None = None,   #  new, defaults to BTC bound
    expected_last: datetime | None = None,    #  new, defaults to BTC bound
):
    first = DATASET_FIRST if expected_first is None else expected_first
    last  = DATASET_LAST  if expected_last  is None else expected_last
    ...
```

Why this preserves frozen BTC research semantics exactly:

| Property | Why it holds |
|---|---|
| BTC default behaviour identical | `None` resolves to the existing module constants; the BTC call site is unchanged |
| No existing test perturbed | Every current caller omits the new arguments, so the branch taken is the original one |
| No frozen artifact touched | Pure source change; no dataset, config or result is regenerated |
| BTC error messages preserved | The message text still interpolates the same bound values |
| Fail-closed preserved | Unset bounds still fall back to BTC constants rather than becoming permissive `None` skips — the opposite of an `expected_count=None` bypass |

That last row matters. Allowing `expected_first=None` to mean *"don't check"*
would introduce exactly the kind of caller-supplied bypass that
`researchguard.py` L27–28 says is deliberately absent. The new parameters must
default to the BTC constants, never to "unchecked".

**Better still**, rather than passing bounds by hand, derive them from the
reservation entry in `research_registry.json`
(`warmup_first`, `warmup_last`, `warmup_bars`, `dataset_sha256`). Then the
validator checks the dataset against **its own reservation**, and BTC keeps
working through its existing default constants. That makes the reservation the
single source of identity rather than a duplicate constant in two places.

**Residual risk:** the docstring says *"Validate the Phase 13 dataset"*, and
`DATASET_*` names imply a single dataset. Broadening the function without
renaming or re-documenting would leave a misleading API. Renaming touches
`__all__` and call sites, so it is a judgement call for the implementing phase,
not something to slip in silently.

**Not implemented here.** Phase 53 is a design document.

---

## 3. Option A — single pre-registered ETH evaluation window

Run `run_backtest` once over the reserved evaluation window under a
`ResearchContext`, with a `CrossAssetAuthorization` recording that a
BTC-labelled configuration is being applied to ETH data.

**Strengths**

- Executable today. No engine change, no frozen-code risk, no test-surface risk.
- Maximises the reserved evidence: **6,744 bars**, 2026-01-01 → 2026-10-08.
- The reservation already describes exactly this run: warm-up 17,544 bars,
  evaluation 6,744 bars, start index 17,544. No new data is required.
- One pre-specified decision rule is unambiguous. No aggregation ambiguity.
- Mirrors the BTC holdout protocol, so ETH is directly comparable to the
  recorded `INCONCLUSIVE` result.

**Limitations**

- **A single window cannot distinguish skill from regime.** One contiguous
  2026 stretch says nothing about behaviour in a different market regime.
- Trade clustering. Phase 30 recorded, for BTC, that trades are *mechanically
  clustered and not independent*. That constraint transfers to ETH: the
  effective independent sample is far smaller than the raw trade count.
- No robustness evidence. One window cannot show stability across sub-periods.
- Single point of failure — one anomaly in 2026 determines the verdict.

**Leakage and reuse risks**

- **BTC holdout reuse: prohibited.** It is `consumed`; `consumed_windows` records
  it and the guard will refuse. ETH must stand alone.
- **Warm-up bars 0…17,543 produce no trades.** They are indicator context only.
  They must not be traded or counted.
- **BTC-informed parameters.** The configuration was developed on BTC
  2024–2025. Applying it unchanged to ETH is legitimate cross-asset transfer
  *only if* explicitly authorised — hence `CrossAssetAuthorization`. Without it,
  the result is unlabelled cross-asset reuse.
- If the result is disappointing, the temptation to re-run with variants is the
  central post-hoc risk. The guard permits exactly one consumption.

**Supported conclusions:** "under this pre-registered configuration, on this
reserved ETH window, at these costs, the measured result was X." Plus a limited
generalisability claim about BTC→ETH transfer.

**Not supported:** that the strategy works generally; that 2026 ETH conditions
predict other regimes; any statement about other assets; any profitability claim
beyond the single window.

---

## 4. Option B — separately designed asset-agnostic walk-forward framework

Make `validate_dataset_integrity` asset-agnostic per §2, source expected bounds
from the registry, and evaluate ETH across multiple walk-forward segments.

**Strengths**

- Regime diversity: multiple out-of-sample segments test stability across
  different market states.
- More independent evidence than one window, and a natural home for
  `assert_no_state_carry()` and fingerprint checks.
- Produces the asset-agnostic machinery the project will need for any future
  instrument, not just ETH.
- Distinguishes "worked in one stretch" from "worked across several".

**Limitations — and one that is easy to miss**

- **The strategy has no training step.** There is no parameter fitting anywhere:
  `lookback`, `fast_period`, `slow_period` and the thresholds are fixed
  constants, and the README states optimization frameworks are deliberately
  excluded. Walk-forward's usual justification — fit on train, test on
  validation — therefore **does not apply**. What Option B actually buys is
  *segmented out-of-sample evaluation*, not out-of-sample generalisation from
  fitting. Describing it as "walk-forward" overstates what is happening, and the
  preregistration must describe it accurately.
- **Multiplicity is the real danger.** Evaluating N segments and reporting the
  best is p-hacking with extra steps. An aggregation rule must be pre-specified
  (e.g. evaluate all segments, report the pooled result, never select on
  outcome). Without that rule Option B is *more* dangerous than Option A.
- **Window sizing.** 6,744 evaluation bars across multiple segments leaves few
  bars per segment. The BTC holdout produced 20 trades from 912 bars; segments
  of comparable size would yield too few trades to support any inference, and
  trades clustered within segments are not independent evidence.
- **Cost.** Engine changes, `__all__` and docstring updates, new tests for the
  new parameters, and re-validation that BTC behaviour is byte-identical.
- **Reserved data is finite.** Carving 2026 into segments consumes the entire
  reserved window at once, with no second chance. A botched Option B run spends
  the evidence permanently.

**Leakage and reuse risks**

- All of Option A's, plus: parameter tuning against segment outcomes; selecting
  a favourable subset of segments; adjusting segment boundaries after seeing
  results (boundary choice determines trade counts materially).
- `WARMUP_RULE = "full_preceding_series"` means each segment warms up on its own
  preceding bars — correct, but it means segment boundaries consume warm-up
  capacity, shrinking usable evaluation bars.

**Data requirements:** the existing ETH reservation is sufficient for segmented
evaluation, but *additional untouched windows* would need fresh acquisition and
their own reservations. Option B's full value is not reachable from the reserved
window alone.

**Supported conclusions:** "under this configuration, results were consistent
across N pre-specified out-of-sample segments on ETH." A materially stronger
robustness claim than Option A.

**Not supported:** generalisation to unseen regimes beyond those segments;
any claim about parameters that were never fitted.

---

## 5. Comparison

| Dimension | Option A (single window) | Option B (segmented) |
|---|---|---|
| Implementable now | Yes | No — engine change required |
| Frozen BTC risk | None | Low if defaults preserved; non-zero if renamed carelessly |
| Reserved bars used | 6,744 | Same 6,744, fragmented |
| Regime diversity | None | Multiple segments |
| Independent-sample gain | None | Modest (clustering persists) |
| Post-hoc abuse risk | Low — one result | **High** unless aggregation is pre-specified |
| Evidence strength | One pre-registered observation | Robustness across segments |
| Reversibility | Reservation consumed once | Reservation consumed once, with more ways to waste it |
| Second attempt possible | No | No |

---

## 6. Recommendation

**Adopt Option A for the reserved window. Design Option B separately, as its
own phase, for future instruments — and do not run it on the reserved ETH
window.**

Rationale:

1. **Option B does not buy what its name implies.** With no fitted parameters,
   walk-forward here is segmented evaluation wearing a generalisation
   costume. The scientific gain is real but smaller than the machinery suggests.
2. **Option B's risk profile is worse precisely where Option A's is not.** More
   segments means more chances to select favourably, and the reserved evidence
   cannot be recovered once spent.
3. **Option A is executable with zero engine change**, so it converts existing
   frozen, checksum-verified evidence into a result without touching frozen BTC
   research semantics at all.
4. **The cross-asset transfer claim is the actual scientific question.** Whether
   a BTC-derived configuration transfers to ETH is best answered once, cleanly,
   with a pre-registered rule — not answered N times with segment selection
   available.
5. **Option B remains the right long-term direction.** The §2 change is small and
   safe. It should be made deliberately, with the asset-agnostic API, the
   registry-sourced bounds, and its own test coverage — not as a prerequisite
   bolted onto a live evaluation.

**If Option B is nonetheless chosen**, it must first have pre-specified: segment
count and boundaries, the aggregation rule, the minimum-trade threshold, and an
explicit statement that segments are never selected on outcome.

**Approval required.** Nothing in this section authorises an evaluation. ETH
remains blocked behind the eight Phase 51 decisions, a frozen preregistration
with an assigned ID, a recorded `CrossAssetAuthorization`, and separate evaluate
authorisation. `RESERVED` is a marker, not a lock — its own note says it is
*"NOT protected against evaluation until a preregistration is frozen and the
guard is exercised."*