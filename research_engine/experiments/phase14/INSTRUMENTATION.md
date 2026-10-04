# Phase 14B — Entry-Time Feature Instrumentation

Status: implementation and tests complete. No outcome analysis performed.

## Purpose

Phase 14 needs to ask whether entry-time conditions relate to how trades
turned out. Phase 13 could not answer that, because the recorded trades kept
only the categorical `trend` and `breakout` / `retest` booleans. A boolean
says *whether* a level broke, not *by how much*, so it cannot support any
statement about magnitude.

Phase 14B adds the missing numeric context. It is deliberately the
smallest step that makes Phase 14C possible, and nothing more:

- **In scope:** recording entry-time features that are knowable before the fill.
- **Out of scope:** looking at any outcome, testing any association,
  tuning any threshold, or changing how the strategy trades.

No result file, `SUMMARY.md`, or performance figure is produced by this phase.
Creating one here would mean reading outcomes before the instrumentation was
fixed, which is precisely the ordering this project has avoided so far.

## The information boundary

This is the constraint that matters most, so it is stated first.

The backtest harness evaluates each candidate candle `i` by calling
`analyze(candles[:i], config)` and then filling at `candles[i].open`. So for an
entry stamped `t`:

| Candle | Role | May be read? |
| --- | --- | --- |
| `candles[i-2]` | `previous` | yes |
| `candles[i-1]` | `current` — last **closed** candle, carries the signal | yes |
| `candles[i]` | `entry` — provides the fill price | **no** |
| `candles[i+1…]` | future | **no** |

Every field below is computed from `previous`, `current`, or the trailing
window ending at `current`. Nothing reads `candles[i]` or later.

The one-candle gap is deliberate and is not a bug: at decision time
`candles[i]` has not closed, so its close is unknowable even though its open
will be used as the fill. Reading it would be lookahead.

This boundary is enforced by test, not just by convention. The decisive test
mutates every candle *after* an entry and requires the entry's recorded fields
to be bit-identical; see "How this is verified".

## Fields

Added to `Signal` (what the strategy decided) and copied onto `PaperTrade`
(what actually happened, so the values survive independently of the `Signal`
object).

| Field | Type | Definition |
| --- | --- | --- |
| `signal_close` | `float` | Close of `current`, the signal candle. |
| `trend_state` | `"up"` / `"down"` / `"sideways"` | The categorical trend in force. Same value as the pre-existing `Signal.trend`; recorded separately so downstream records need not reach back to the signal object. |
| `breakout_distance` | `float` | How far the breakout extended beyond the level it broke, as a fraction of that level. Measured on the candle that *broke out*, which differs by entry kind — see below. Always positive when present. |
| `retest_distance` | `float` | How far the retest candle reached back toward the broken level, as a fraction of that level. Non-negative. |
| `realised_volatility` | `float` | Sample standard deviation of the trailing simple returns. **Not annualised** — the period is stated in the field's definition, so it must not be compared against an annualised figure. |
| `mean_range` | `float` | Mean high-low range over the trailing window. |
| `support_at_entry` | `float` | Support level in force at signal time. |
| `resistance_at_entry` | `float` | Resistance level in force at signal time. |

### Which candle each distance is measured on

This is the detail most likely to be misread, so it is explicit.

`breakout_distance` — the candle that broke the level depends on the entry:

| Entry kind | Measured on | Long | Short |
| --- | --- | --- | --- |
| `bullish retest` / `bearish retest` | `previous` — the candle that broke out | `(previous.close - resistance) / resistance` | `(support - previous.close) / support` |
| `uptrend breakout` / `downtrend breakdown` | `current` — the signal candle itself | `(current.close - resistance) / resistance` | `(support - current.close) / support` |

For a retest entry the breakout happened on an earlier candle, so measuring it
on the signal candle would report the wrong quantity. For a breakout entry the
breakout is happening now.

`retest_distance` — measured on `current`, and on whichever leg the existing
gate uses:

- baseline (`retest_use_close=False`, the committed default): the **wick**.
  Long uses `current.low`; short uses `current.high`.
- `retest_use_close=True`: the **close** instead.

The recorded value always tracks the leg the gate actually used, so the field
cannot silently disagree with the decision that produced it.

### Why these denominators

Distances are normalised by the level itself, so a distance means "this
fraction beyond the level" and is comparable across levels and across the
price scale of the series. An absolute price distance would not be.

### Why `realised_volatility` uses the trailing close

The strategy's entire state derives from closes: support and resistance come
from trailing highs and lows, the gates read closes, and the moving averages
that set `trend_state` are built from closes. Volatility measured from closes
therefore sits in the same information space as the rest of the decision.

`mean_range` is the exception: it reads highs and lows because a range
statistic that ignored them would not be a range. It stays causal because
`high` and `low` of `current` are known once that candle has closed.

### `mean_range` is not ATR

It is the mean of `(high - low)` over the trailing window. True range needs
the previous close to account for gaps between sessions, and that is not
implemented anywhere in this repository. Naming it ATR would misdescribe it,
so it is not named ATR. It is a deliberately cruder range proxy.

### `realised_volatility` is not ATR, and is not annualised

It is `statistics.stdev` of consecutive simple returns over the trailing
`period` closes. Not annualised, not scaled by √period. The value is a
per-period dispersion in the same units as a simple return.

### When a field is `None`

`None` means *not applicable* or *not computable*. It never means zero.

- `breakout_distance` is `None` for a `flat` signal — there was no breakout to
  measure.
- `retest_distance` is `None` unless the entry was a retest.
- `realised_volatility` is `None` when fewer than `period + 1` candles are
  available, since `period` returns need `period + 1` closes.
- `mean_range` is `None` when there are no candles.
- `trend_state` is `None` only on a hand-constructed `Signal`; a real signal
  always has one.

Substituting `0.0` for a missing measurement would make "no breakout" and "a
breakout of zero size" indistinguishable, which is exactly the confusion these
fields exist to remove.

Worth noting: `analyze` requires at least 22 candles while a 20-period
volatility needs 21, so **any signal the strategy can actually emit has both
trailing-window features populated**. The `None` branch is reachable only by
calling the indicator helpers directly with insufficient history. That is
tested rather than assumed.

## Behaviour preservation

Instrumentation is additive and observational. Nothing was changed that could
alter a decision, a fill, a position size, a cost, or an exit.

- New indicator functions are pure additions; no existing indicator changed.
- `Signal` and `PaperTrade` gained **defaulted** fields, so existing
  construction sites are unaffected.
- The breakout/retest gates were rewritten to call two local helpers,
  `distance_above` and `distance_below`, which contain the *same* arithmetic
  the inline comparisons used. This is a readability refactor with identical
  semantics; it exists so the recorded distance and the gate threshold are
  literally the same expression and cannot drift apart.
- The simulator copies fields onto the trade after `quantity` is computed and
  reads none of them.
- No `StrategyConfig` default, dataset, window definition, or cost assumption
  was altered.

Proof: all six frozen Phase 13 baseline windows re-run to the **same trade
count and the same ending balance as the committed result file, to within
1e-9**. That is checked by a test, not by inspection.

## How this is verified

`research_engine/tests/test_entry_time_features.py`. Three obligations:

**Causality.** The decisive test corrupts every candle after an entry boundary
and requires each pre-boundary trade's recorded fields to be bit-identical.
Because the corrupted prices are shifted far enough to change any outcome,
this is a strong test rather than a formality. The converse is also tested:
mutating a *pre-entry* candle must change the relevant feature. A test that
only proved features were insensitive to everything would pass just as
readily.

**Behaviour preservation.** Frozen Phase 13 reproduction, explicit assertions
on every `StrategyConfig` default, the harness constants, and the execution
costs.

**Discrimination.** Each field is anchored to the raw candles independently of
the implementation, so a test cannot pass merely by restating the code. Signal
decisions are compared against an independent reimplementation of the
documented gates.

The suite was mutation-tested. 31 deliberately introduced defects were checked;
**all 31 are caught**. They covered:

- lookahead — including the entry candle in the signal window, and each
  trailing-window indicator dropping or gaining a candle;
- propagation — a field dropped from the trade, or copied from the *wrong*
  signal attribute;
- unavailable-value handling — `None` replaced by `0.0`;
- distance semantics — losing `abs()`, wick swapped for close, the sign
  flipped, or measured on the wrong candle;
- gate changes — each `StrategyConfig` threshold, and `>` slipping to `>=`;
- execution — fill reference, sizing, fee, slippage, risk fraction, execution
  model.

Three mutants initially survived and drove real test additions: a wrong-field
copy, a lost `abs()` on the short retest, and a breakout distance measured on
the wrong candle. Two early mutation runs were also discarded — the first
because a copied sandbox without `pyproject.toml` silently imported the real
installed package, making every mutation a no-op, and the second because a
timed-out run left a mutated file behind. Both were caught by diffing the
sandbox against the working tree before trusting results.

No linter is configured in this repository, so no lint step was run.

## Deliberate non-goals

Not added, and why:

- **MAE / MFE.** Maximum adverse and favourable excursion are computed from
  candles *after* entry. Recording them here would mean shipping post-entry
  data alongside entry-time data, inviting exactly the confusion this phase
  exists to prevent. They belong in a later phase, stored separately and
  labelled as outcome-side.
- **Any outcome field.** No win/loss label, score, rank, bucket, regime label
  or edge indicator. A test asserts none exists on `Signal` or `PaperTrade`.
- **Any threshold change.** Choosing a distance cut-off requires looking at
  outcomes. That is Phase 14C at the earliest, and it must not be smuggled in
  here as a "default".
- **Annualisation, ATR, or indicator variants.** Alternatives cannot be
  selected without comparing them, which needs outcomes.
- **Per-window or per-trade aggregation.** Nothing is summarised or bucketed.

## What Phase 14C may now do

With these fields recorded, a later phase can ask descriptive questions about
the *existing* committed strategy — for example whether larger breakout
distances were associated with different outcomes. Three constraints carry
forward:

1. The fields are descriptive. Turning any of them into a trading rule is a
   new strategy requiring its own out-of-sample validation, not a finding.
2. `None` must be handled as a distinct category, never imputed to zero.
3. Sample sizes are small. Phase 13 produced 267 baseline trades across six
   windows. Any subgroup with a handful of trades is noise, and must be
   reported as such rather than mined for a pattern.

Any threshold selected from observed outcomes is in-sample by construction and
must be labelled so.