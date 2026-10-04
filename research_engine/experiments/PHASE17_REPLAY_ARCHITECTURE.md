# Phase 17A — Paper Replay Architecture and Contract

**Status:** design only. No code in this document has been implemented.
**Date:** Phase 17A
**Predecessor:** Phase 16 checkpoint `3d0b517785033bef486df91e855e01915f9ae3b0`
**Related documents:** `PAPER_TRADING_ARCHITECTURE.md`, `PAPER_TRADING_INTEGRATION_PLAN.md`
**Codebase state at time of writing:** 834 tests passing, working tree clean.

---

## 0. Scope, method and reading instructions

This document defines what a paper replay is, how it must advance, what state it
owns, and what it must never do — **before** any of it is written.

### 0.1 Method

Every execution rule below was read out of the implementation, not inferred from
a document. Where this document states a rule, it cites the file and line that
produces it. Where the implementation is genuinely ambiguous or contradicts a
planning document, §26 records it as an open question **instead of silently
choosing a behaviour**.

The three authoritative sources for execution semantics, in priority order:

1. `crypto_paper_lab/backtest.py` — the loop that defines ordering and timing.
2. `crypto_paper_lab/simulator.py` — `PaperBroker`, which defines fills, sizing
   and accounting.
3. `crypto_paper_lab/models.py` — the `Candle` / `Signal` / `PaperTrade` shapes.

### 0.2 Terminology used throughout

| Term | Meaning in this document |
|---|---|
| **signal bar** | The newest candle visible to `analyze()`. Its timestamp is `Signal.timestamp`. |
| **execution bar** | The candle whose **open** supplies the fill price. Its timestamp becomes `PaperTrade.entry_time` / `exit_time`. |
| **cursor `i`** | The index of the execution bar the next step will consume. |
| **step** | One iteration of the `run_backtest` loop, made callable. |

> **Naming hazard, stated once and meant to be remembered.** `run_backtest`
> binds the name `current` to the **execution** bar (`backtest.py:136`).
> `strategy.analyze` binds the name `current` to the **signal** bar
> (`strategy.py:60`). These are *different bars*. The gap between them is the
> whole causality boundary. Any replay implementation that reuses one name for
> both will be off by one bar. Replay should therefore use the explicit terms
> *signal bar* and *execution bar* and never a bare `current`.

### 0.3 What this document is not

It does not specify a UI layout, an OpenAPI schema, a persistence format, or a
deployment story. It specifies **behaviour and boundaries** so that Phase 17B
onward can be written against something checkable.

---

## 1. Replay purpose

### 1.1 Definition

> **Paper replay** is the controlled, step-at-a-time advance of a paper-trading
> session through an **already-closed historical candle series**, where each
> step evaluates the existing strategy on the bars visible so far and, subject
> to an explicit execution policy, performs a **simulated** fill at the next
> bar's open.

Three properties are definitional, not incidental:

1. The candles are **historical**. They have already happened. Nothing is
   predicted, forecast or anticipated.
2. Progression is **caller-driven** — one step, or a bounded batch — and is
   deterministic for a given `(cursor, broker state, dataset)`.
3. Every resulting trade is **simulated**. No money, no venue, no order.

### 1.2 What replay is not

Replay is **not** evidence that the strategy works. It replays a period that
already occurred, with fills the market is assumed to have offered at bar
opens. Section 27 restates this as a standing constraint.

### 1.3 Four concepts that must not be merged

These are routinely conflated. They are distinct here, and the API surface,
state model and test plan all keep them separate.

| Concept | What it is | Replay's relationship to it |
|---|---|---|
| **Historical replay** | Re-walking closed candles, one step at a time, with full control over pacing. *This document.* | — |
| **Backtest** | `run_backtest`: the same loop, run to completion in one call, returning an aggregate `BacktestResult`. | Replay is the backtest loop made callable per iteration. Replay over N steps **must** equal the corresponding prefix of a backtest (§4.9). |
| **Paper execution** | A simulated fill performed by `PaperBroker.open_from_signal` / `PaperBroker.close`. | Replay *may* trigger paper execution, but only via an explicit policy (§16). Execution is a separate concern from progression (§3). |
| **Future / live market data** | Data not yet known, arriving over time. | **Out of scope, permanently, for Phase 17.** No endpoint, mode or code path may fetch, poll, subscribe to or infer a future price. The dataset is historical and frozen. |

The distinction that bites hardest in practice: **replay ≠ paper trading on live
data.** A user stepping through 2024 candles is not watching the market, and the
UI must never present a replay cursor as a live price.

---

## 2. Authoritative execution semantics

Preserved verbatim from the existing engine. Replay reproduces these; it never
improves on them.

### 2.1 The canonical loop

`backtest.py:135-205`, reproduced in full because every replay rule derives from it:

```python
minimum_history = max(config.lookback + 2, config.slow_period)      # :112-115

for index in range(minimum_history, len(candles)):                  # :135
    current = candles[index]                                       # :136  EXECUTION bar

    signal = analyze(candles[:index], config)                       # :139  sees 0..index-1

    execution_signal = replace(                                    # :145-149
        signal,
        timestamp=current.timestamp,
        price=current.open,
    )

    if broker.open_trade is not None and entry_index is not None:    # :151
        trade = broker.open_trade
        bars_held = index - entry_index                            # :153
        exit_reason = None

        if bars_held >= 1:                                         # :158
            closed_bar = candles[index - 1]                         # :159

            if (config.max_holding_bars is not None
                    and bars_held >= config.max_holding_bars):     # :161-165
                exit_reason = MAX_HOLDING
            elif (config.stop_loss_pct is not None
                    or config.take_profit_pct is not None):        # :166-174
                stop_hit, target_hit = _levels_breached(trade, closed_bar, config)
                if stop_hit:
                    exit_reason = STOP_LOSS
                elif target_hit:
                    exit_reason = TAKE_PROFIT

        if exit_reason is None and (                                # :177-181
            signal.side in {"long", "short"}
            and signal.side != trade.side
        ):
            exit_reason = OPPOSITE_SIGNAL

        if exit_reason is not None:                                 # :183
            trade = broker.close(current.open, current.timestamp)   # :184-187
            trade.exit_reason = exit_reason
            trade.bars_held = bars_held
            entry_index = None

    if (broker.open_trade is None                                    # :195-205
            and signal.side in {"long", "short"}
            and _side_allowed(signal.side, config)
            and (evaluation_start is None or index >= evaluation_start)):
        broker.open_from_signal(execution_signal, risk_fraction=risk_fraction)
        entry_index = index

if broker.open_trade is not None:                                   # :207-213
    last = candles[-1]
    trade = broker.close(last.close, last.timestamp)
    trade.exit_reason = END_OF_DATA
    trade.bars_held = len(candles) - 1 - (entry_index or 0)
```

### 2.2 Field-by-field contract

| Semantics | Rule | Source |
|---|---|---|
| **Signal candle** | `candles[i-1]`. `analyze` receives `candles[:i]`, so its newest input is index `i-1`. | `backtest.py:139` |
| **Next-candle execution** | Always. A signal observed at bar `i-1` fills at bar `i`. | `backtest.py:145-149` |
| **Open-price execution** | Fill reference is `candles[i].open` for both entry and exit. | `backtest.py:148`, `:185` |
| **Fee treatment** | `fee_total = (entry_value + exit_value) * fee_rate`, i.e. charged on **filled** notional, once per leg. A round trip therefore pays `fee_rate` twice. | `simulator.py:160-162`, `costs.py:21-23` |
| **Slippage treatment** | Model-dependent. Under `cost_deduction` it is **deducted** from P&L. Under `fill_price` it is embedded in the fill price and only *attributed* for reporting. | `simulator.py:180-189` vs `:164-179` |
| **Spread treatment** | `0.0` under `cost_deduction` — the engine **rejects** a non-zero spread there to prevent double counting. Only meaningful under `fill_price`. | `costs.py:77-82`, `simulator.py:185` |
| **`execution_model`** | `"cost_deduction"` (default, frozen) or `"fill_price"`. Selects whether friction lands in the price or in P&L. | `costs.py:8-12`, `:60` |
| **Position sizing** | `quantity = (self.cash * risk_fraction) / fill`. Uses **cash**, not equity. `risk_fraction` defaults to `0.01` and must satisfy `0 < r <= 1`. | `simulator.py:92`, `:82-83` |
| **Single-position constraint** | `open_from_signal` raises `ValueError("a paper trade is already open")` if a trade is open. The loop additionally guards with `broker.open_trade is None`. **Per broker**, not global — see §14. | `simulator.py:79-80`, `backtest.py:196` |
| **LONG / SHORT behaviour** | Identical logic, mirrored direction. `is_buy = (side == "long") == entering` under `fill_price`; `direction = 1 if side == "long" else -1` in P&L. Both models apply friction adversely on every leg. | `simulator.py:64`, `models.py:122`, `simulator.py:28-30` |
| **Flat signal** | Cannot open. `open_from_signal` raises `ValueError("flat signals cannot open a paper trade")`. | `simulator.py:76-77` |
| **Stop-loss / take-profit** | Disabled by default (`None`). Detection on the **closed** signal bar `candles[i-1]`; fill at the **next** bar's open. Measured from `trade.entry_price` — the recorded fill, not the raw reference. | `backtest.py:166-174`, `:27-62` |
| **Stop vs target on one bar** | **Stop assumed first.** Conservative. Because the fill is the next open either way, P&L is unaffected; only the `exit_reason` label differs. | `backtest.py:170-174` |
| **Same-bar exit rule guard** | Exit rules are skipped when `bars_held < 1`, so a position can never be exited on its own entry bar. | `backtest.py:158` |
| **Maximum holding** | Disabled by default (`None`). When set, fires at `bars_held >= max_holding_bars`, checked **before** stop/target. | `backtest.py:161-165` |
| **Opposite-signal exit** | The baseline rule. Fires when the signal is `long`/`short` and differs from the open trade's side. Checked **last**, only if no optional rule already fired. | `backtest.py:177-181` |
| **Cash accounting** | `cash += net_pnl` on close only (`simulator.py:191`). **No cash is reserved at entry** — this is a quantity model, not the dashboard mock's reservation model. | `simulator.py:191`, `PAPER_TRADING_ARCHITECTURE.md:33-36` |
| **Equity** | Does not exist. There is no unrealized P&L on a broker and no margin concept. | `simulator.py` (absent) |
| **End-of-data closure** | After the loop, any open trade is force-closed at the **final candle's close** (not its open) with `exit_reason = "end_of_data"`. | `backtest.py:207-213` |
| **`allowed_sides`** | Gates **entries only**. An open position still exits on an opposite-side signal. `None` allows both. | `backtest.py:19-24`, `:198` |
| **`evaluation_start`** | Entries require `index >= evaluation_start`. Earlier candles still warm indicators. | `backtest.py:94-100`, `:199` |

### 2.3 Behaviours that look like bugs and must be reproduced

These are recorded so a future implementer does not "fix" them.

**(a) A single step can close one position and open another — and this is the
dominant case, not an edge case.**
The exit block (`backtest.py:151-193`) and the entry block (`backtest.py:196-205`)
are sequential, not exclusive. After a close sets `broker.open_trade = None`, the
entry block is reached in the **same iteration** with the **same `signal`**. A
long position closed by a short signal is immediately replaced by a short at the
same `candles[i].open`. This is a same-bar reversal.

Measured on the frozen baseline (`run_backtest` over all 17,544 candles):
**343 of the 344 closed trades are immediately followed by a new entry at the
identical timestamp.** Practically every `opposite_signal` exit is a reversal,
not a flat period. A replay model or UI that assumes "one event per step" is
wrong about the common case, not merely an edge case.

**(b) End-of-data *can* open and close on the same candle — but does not, on the
frozen baseline.**
The loop's final iteration is `i = len(candles) - 1`. If it opened a position
there, the post-loop block (`backtest.py:207-213`) would close it at the same
bar's **close**, yielding `bars_held = len(candles) - 1 - entry_index = 0`. So
the code path permits `end_of_data` with `bars_held == 0`.

However, this does **not** occur in the recorded run: the frozen baseline
produces exactly **one** `end_of_data` trade, with `bars_held > 0` — a position
that genuinely survived to the final bar. The distinction matters for two
reasons: a replay implementation must still *permit* the `bars_held == 0` case
because a different dataset or configuration could reach it, and a UI must not
be built on the assumption that `end_of_data` always implies a surviving
position.

**(c) `bars_held` is written by the caller, not the broker.**
`PaperBroker.close` does not set `bars_held` (`simulator.py:118-196`). Both
`run_backtest` and replay must assign it after the close returns. An open trade's
`bars_held` is therefore `0` by dataclass default — this is why Phase 16E's
`/api/position` omits the field.

**(d) `exit_reason` is an unconstrained string.**
`models.py:75` declares `exit_reason: str = ""`. The named constants in
`backtest.py:12-16` are conventions, not an enforced enumeration. A new label
(for example an operator-initiated close) is representable **without any engine
change** — see §14.3.

**(e) Statistics drift by one ULP between two engine functions.**
`stats.performance` sums net P&L from `0.0`; `PaperBroker` accumulates it onto
the opening cash. Measured relative divergence: **9.16e-14**. Replay will
inherit this. It must not "fix" it by having one layer override the other.

---

## 3. One replay step

### 3.1 Definition

> **One step** consumes exactly one execution bar — advancing the cursor from
> `i` to `i + 1` — and performs, in this exact order: signal evaluation on bars
> `0..i-1`, exit evaluation, entry evaluation, state update, cursor advance.

The order is not a convenience. It is the order of `backtest.py:135-205`, and
changing it changes results.

### 3.2 The step sequence

```
STEP(cursor = i)

  GUARD
    if i >= len(candles):            -> finish (EOD, §3.7), do not advance

  DATA
    execution_bar = candles[i]                    # provides the fill price
    visible       = candles[:i]                   # causality boundary (§4)

  SIGNAL
    signal = analyze(visible, config)
      -> newest visible bar is candles[i-1] = the signal bar
      -> may raise ValueError if len(visible) < minimum_history (§26.8)

  EXECUTION — exit evaluation (only if open_trade is not None)
    bars_held = i - entry_index
    exit_reason = None
    if bars_held >= 1:
        closed_bar = candles[i-1]                 # the signal bar
        if max_holding_bars is not None and bars_held >= max_holding_bars:
            exit_reason = "max_holding"
        elif stop_loss_pct or take_profit_pct:
            stop_hit, target_hit = levels_breached(open_trade, closed_bar)
            if stop_hit:      exit_reason = "stop_loss"
            elif target_hit:  exit_reason = "take_profit"
    if exit_reason is None and signal.side in {long, short} \
                       and signal.side != open_trade.side:
        exit_reason = "opposite_signal"
    if exit_reason is not None:
        trade = broker.close(execution_bar.open, execution_bar.timestamp)
        trade.exit_reason = exit_reason
        trade.bars_held  = bars_held
        entry_index = None

  EXECUTION — entry evaluation (only if open_trade is None, after any close)
    if signal.side in {long, short} \
       and side_allowed(signal.side, config) \
       and i >= evaluation_start:
        broker.open_from_signal(
            replace(signal, timestamp=execution_bar.timestamp,
                           price=execution_bar.open),
            risk_fraction=risk_fraction)
        entry_index = i
      # a 'flat' signal, or a full position, or a disallowed side: no action

  STATE UPDATE
    cursor = i + 1
    last_signal = signal
    (cash / open_trade / journal updated by the broker, never by replay)

  EXPOSE
    snapshot -> JSON
```

### 3.3 Answers to the specific questions

| Question | Answer | Source |
|---|---|---|
| Which candle is exposed? | The **execution bar** `candles[i]`, which is complete — it is historical. Its *open* is the only price used this step. | §2.2 |
| Is the candle complete? | Yes. All replay candles are closed bars. There is no partial or forming candle anywhere in this design. | §1.1 |
| When is the strategy evaluated? | Once per step, on `candles[:i]`, before any fill. The strategy **never** sees the execution bar. | `backtest.py:139` |
| When can a signal be generated? | Every step, from index `minimum_history` onward. A signal may be `flat`, which is a valid observation and never a trade. | `strategy.py:53-58`, `:191-192` |
| When can a paper fill occur? | Only after signal evaluation, at `candles[i].open`. Never intrabar, never on a high/low. | `backtest.py:148`, `:185` |
| **Can a fill happen on the same candle as the signal?** | **No.** A signal from signal bar `i-1` fills at execution bar `i`. One bar, never zero. This is the causality guarantee and the reason replay cannot be trivially "optimistic". | §4 |
| What if a position is already open? | The entry block is skipped entirely. No pyramiding, no averaging, no second position. `open_from_signal` would raise; replay never reaches it in that state. | `backtest.py:196`, `simulator.py:79-80` |
| What state changes after one step? | `cursor` (+1), `last_signal`, and whatever the broker changed: `open_trade`, `cash`, `journal`. Replay itself mutates nothing else. | §5 |

### 3.4 A step can contain two fills

Because exit and entry blocks are sequential (§2.3a), **one step can close one
position and open another at the same `candles[i].open`**. This is the normal
case, not a rare one — 343 of 344 trades in the frozen baseline participate in a
same-bar reversal. Replay's step contract must therefore permit **up to two**
broker mutations per step: one `close` and one `open`. A test model, UI
transition or event log that assumes "at most one event per step" will be wrong
about the common path.

### 3.5 `flat` is a real outcome

`analyze` returns `side="flat", reason="no confirmed breakout or retest"` in the
default case (`strategy.py:191-192`). A flat step mutates only the cursor and
`last_signal`. It is **not** an error, and it must not be reported as one.

### 3.6 No accidental optimisation

Replay must never be "improved" to fill on the signal bar's close, to fill at a
better price, or to skip the one-bar delay. Any such change is a strategy-behaviour
change and belongs in a research phase with its own equivalence proof, not in a
UI-enabling phase.

### 3.7 End-of-data within a step

When `cursor >= len(candles)` there is no execution bar. Replay transitions to
`finished` (§7.6) rather than stepping. Any open position is force-closed at the
**final candle's close** with `exit_reason = "end_of_data"` and
`bars_held = len(candles) - 1 - entry_index`, exactly as `backtest.py:207-213`.
A step attempted while `finished` is an **error**, not a silent no-op — a silent
no-op would let a UI believe it advanced (§22, `REPLAY_FINISHED`).

### 3.8 Start index

The loop begins at `minimum_history = max(lookback + 2, slow_period)` = **22**
for the frozen baseline (`backtest.py:112-115`, `signals.py:45-53`).

Replay's `start_index` may be **greater** than `minimum_history` — a walk-forward
evaluation boundary is the motivating case. This is safe precisely because the
broker starts flat: skipping iterations can skip an *exit* decision, but there is
no open position to exit. Starting below `minimum_history` is invalid and must be
rejected explicitly rather than surfacing as `analyze`'s generic `ValueError`.

---

## 4. Candle index and causality

### 4.1 Cursor semantics

| Cursor value | Means |
|---|---|
| `cursor = start_index` | Nothing consumed. The next step will fill at `candles[start_index].open`. |
| `cursor = i` (mid-replay) | Bars `candles[0 .. i-1]` are fully consumed. The next step's signal sees exactly those bars and fills at `candles[i].open`. |
| `cursor = len(candles)` | Finished. All bars consumed; end-of-data closure already applied. |

### 4.2 Visibility rules

| Candle index `j` relative to cursor `i` | Visible to `analyze`? | Usable as a fill price this step? |
|---|---|---|
| `j < i - 1` | Yes — history, indicator warm-up | No |
| `j = i - 1` | Yes — **the signal bar** | No |
| `j = i` | **No** | Yes — **the execution bar**, `.open` only |
| `j > i` | **No** | No |

### 4.3 Anti-lookahead invariant

> **ALI-1 (signal causality).** For any cursor `i`, the signal computed at step
> `i` is a function of `candles[0 .. i-1]` and the strategy configuration, and of
> nothing else. Formally `signal(i) = analyze(candles[:i], config)`.

> **ALI-2 (fill locality).** For any cursor `i`, the only execution-bar value
> that can affect step `i` is `candles[i].open`.

> **ALI-3 (state locality).** For any cursor `i` and any `N >= i`, the replay
> state after `N` steps depends only on `candles[0 .. N-1]`.

**How ALI-1 is enforced, not merely intended:** the boundary is the *slice*
`candles[:i]` passed to `analyze`. `analyze` cannot observe later bars because
they are not in the object it receives. This is a structural guarantee, not a
convention — which is precisely why replay must pass a slice and must never pass
the full series with a separate index argument.

### 4.4 The test that proves it

The brief requires a test showing that changing candles after the replay point
cannot change the current signal. Three tests, in increasing strength:

**T1 — Signal invariance (proves ALI-1).**
For a fixed cursor `i` and dataset `C`, build `C'` by replacing every candle at
index `>= i` with adversarial values (a constant spike; a deep crash; reversed
order). Then `analyze(C[:i], config) == analyze(C'[:i], config)`, field for
field. Because both calls receive structurally identical slices, this must hold
exactly — not approximately.

**T2 — Fill locality (proves ALI-2).**
For a fixed cursor `i`, mutate only `candles[i]` and assert the *signal* is
unchanged while the *fill price* changes. This catches the classic off-by-one
where the implementation passes `candles[:i+1]`.

**T3 — Prefix equivalence (proves ALI-3).**
Run replay to cursor `N` over dataset `C`. Then run replay to the same cursor `N`
over `C''`, where all candles at index `> N` are replaced. Assert the broker
state is **identical**: same cash to the last bit, same journal length, same
`open_trade` fields, same `last_signal`.

**T4 — Backtest equivalence (the strongest form).**
For every `N` in `start_index .. len(candles)`, replaying `N - start_index` steps
must leave the broker in the same state as a `run_backtest` invocation truncated
to the same point. Implemented by running `run_backtest(candles[:K])` for
increasing `K` and comparing. This is the test that would catch *any* accidental
divergence between replay and the research engine, and it is the single most
valuable test in Phase 17.

### 4.5 How the next-candle fill is represented

Not as a pending order. The engine has no order concept. The signal at step `i`
is simply **forgotten** after the step, and the fill happens inside the same step
using `candles[i].open`. Nothing is queued across steps.

The UI should be able to *show* the gap, which is why the integration plan
(§4.2) proposes exposing both `signal_timestamp` and `fill_timestamp`. They
differ by exactly one bar interval (3600 s for this dataset). Phase 16's
`/api/signal` already documents this relationship.

---

## 5. Replay state

The minimum state a step needs. Each field is classified by **provenance**,
because the Phase 16 discipline is that nothing is exposed unless the engine can
authoritatively produce it.

Legend: **[A]** authoritative existing engine state · **[D]** derived ·
**[N]** newly introduced replay state · **[U]** unsupported / must be absent.

| Field | Class | Source / justification |
|---|---|---|
| `replay_id` | **[N]** | New. Identifies the replay lineage (dataset + strategy + costs + start index). Proposed: `uuid4`, minted once at create, retained across reset (§9). `PaperSession.session_id` is the precedent. |
| `mode` | **[N]** | New. Which conceptual mode owns this replay (§12). `None` for a bare replay with no mode attached. |
| `status` | **[N]** | New. `idle \| running \| paused \| finished` (§7). Replay-specific; the engine has no lifecycle. Phase 16's `SessionResponse.state` is hard-coded `Literal["idle"]` and must widen — see §26.3. |
| `cursor` | **[N]** | New. Index of the next execution bar. The engine has no cursor; `run_backtest`'s loop variable is not exposed. |
| `start_index` | **[N]** | New. Where the replay began. Enables walk-forward boundary replay (§3.8). |
| `bars_processed` | **[D]** | `cursor - start_index`. Cheap, useful for the UI. |
| `current_candle` | **[D]** | `candles[cursor - 1]`, the last consumed bar. `None` before the first step. |
| `current_candle_timestamp` | **[D]** | `current_candle.timestamp`. |
| `next_candle_timestamp` | **[D]** | `candles[cursor].timestamp` if in range else `None`. Exposes the one-bar gap. |
| `next_candle_available` | **[D]** | `cursor < len(candles)`. Distinguishes "paused at the end" from "finished". |
| `last_signal` | **[A]** | Verbatim `Signal` from the most recent `analyze` at the **signal bar**. `None` before the first step. Never mutated. |
| `signal_timestamp` | **[A]** | `last_signal.timestamp` — the signal bar. |
| `fill_timestamp` | **[A]** | The execution bar's timestamp, when a fill occurred this step. |
| `starting_balance` | **[A]** | `broker.starting_balance`. |
| `balance` | **[A]** | `broker.cash`. Realized only. |
| `realized_pnl` | **[D]** | `broker.cash - broker.starting_balance`. The engine's own definition (`results.py:21-22`). |
| `open_position` | **[A]** | `broker.open_trade`, or `None`. Same omissions as Phase 16E's `/api/position`: no costs, no `bars_held`, no unrealized P&L — all are unpopulated while open (§2.3c). |
| `trade_count` | **[A]** | `len(broker.journal)`. |
| `trades` | **[A]** | `broker.journal`, verbatim, in append order. |
| `entry_index` | **[N]** | New. Index at which the open trade was entered; required to compute `bars_held`. **Not** derivable from the broker — `PaperTrade` records a timestamp, not an index. This is the one piece of genuinely new bookkeeping replay must own. |
| `evaluation_start` | **[N]** | New. Optional index gate on entries, mirroring `backtest.py:199`. Defaults `None`. |
| `risk_fraction` | **[A]** | `walkforward.RISK_FRACTION` = `0.01`. Recorded, not resettable per mode. |
| `dataset` identity | **[A]** | See §21. SHA-256 + bounds + count, via existing `walkforward` constants. **No path.** |
| `strategy` identity | **[A]** | `config_hash(config)` + `repr(config)`, via `walkforward.config_hash`. |
| `execution` identity | **[A]** | `costs_hash(costs)` + `repr(costs)` + rates, via `walkforward.costs_hash`. |

### 5.1 Fields that must NOT appear

| Field | Why **[U]** |
|---|---|
| `equity` | `balance + unrealized_pnl`; unrealized is unavailable on a broker (§2.2). |
| `unrealized_pnl` | Requires a mark price. Phase 16 deliberately omits it from `/api/position`. `robustness.equity_curve_mark_to_market` exists but is a **post-hoc pass over a candle array**, not a broker method — using it inside a live step would be a new accounting path. |
| `available_balance` | Defined as equity. Unavailable. |
| `reserved_capital` | The engine has **no margin concept**. The dashboard mock's reservation model is one of the four divergences to be deleted (`PAPER_TRADING_ARCHITECTURE.md:33-36`). |
| `margin`, `buying_power`, `notional`, `leverage` | No engine representation. Inventing them is the exact failure the architecture audit identified. |
| `mark_price` / `current_price` | Not a broker concept. |
| `confidence`, `probability`, `expected_return` | Phase 16 already established the engine defines none. |
| `sharpe` / `sortino` / `calmar` | Same. Belong to `/api/statistics` reasoning, which deliberately reports none. |
| `bars_held` (while open) | `0` by default; written only by the caller after a close (§2.3c). |

---

## 6. Signals, execution and the step boundary

`analyze` is a **pure function**. It has no side effects, opens nothing, and
mutates nothing (`strategy.py:49-212`). Everything about "turning a signal into a
trade" is a **policy** layered on top by `run_backtest` (`backtest.py:195-205`).

This is the most important structural fact in the document:

> **Replay must make the execution policy an explicit, swappable object, not an
> inline block copied from `run_backtest`.**

If replay inlines the entry rule, then Manual mode cannot exist (§16), because
"do not trade this signal" would be inexpressible. Phase 16's `paper_api` module
layout — a thin module per concern (`signals.py`, `perfstats.py`, `marketdata.py`)
— is the precedent: the policy belongs in its own module.

The policy receives `(signal, broker, execution_bar, cursor)` and returns a
decision: `OPEN` / `CLOSE` / `HOLD`. It must never compute a price, a size or a
cost itself — those stay inside `PaperBroker`.

---

## 7. Replay lifecycle

### 7.1 States

Four states, and no others. A fifth would be unjustified.

| State | Meaning |
|---|---|
| `idle` | Created and reset. Cursor at `start_index`. No bars consumed. No auto-run timer. |
| `running` | Auto-run active: the replay is being stepped on an interval. |
| `paused` | Auto-run stopped. Cursor and broker state retained. |
| `finished` | Cursor reached `len(candles)`. End-of-data closure applied. Terminal. |

`running` and `paused` describe **the auto-run timer only**. `step()` is legal
from `idle`, `paused` and — deliberately — is *refused* from `finished`. A
manual `step()` from `idle` is legal because stepping once without starting a
timer is a normal way to use replay.

### 6.1 Why not a `stepping` state

Not needed. `step()` is synchronous and returns when the step is done; there is no
observable intermediate. Adding a state for it would be noise.

### 7.2 Transitions

| From | Action | To | Broker mutated? | Notes |
|---|---|---|---|---|
| — | `create` | `idle` | **Yes** (fresh) | New `PaperBroker`, empty journal, `cursor = start_index` |
| `idle` | `start` | `running` | No | Arms the timer. Does not advance. |
| `idle` | `step` | `idle` | **Yes** | Legal. Manual single-step before starting. |
| `idle` | `reset` | `idle` | **Yes** (recreated) | Idempotent no-op state-wise |
| `running` | `pause` | `paused` | No | Disarms the timer |
| `running` | `step` | `running` | **Yes** | Legal; interleaves with the timer |
| `running` | `reset` | `idle` | **Yes** (recreated) | Must first stop the timer |
| `paused` | `start` | `running` | No | Re-arms; resumes from the current cursor |
| `paused` | `step` | `paused` | **Yes** | The main manual-advance path |
| `paused` | `reset` | `idle` | **Yes** (recreated) | |
| `finished` | `reset` | `idle` | **Yes** (recreated) | The **only** way out of `finished` |
| `finished` | `step` | `finished` | No | **Rejected**, `409 REPLAY_FINISHED` |
| `finished` | `start` | `finished` | No | **Rejected**, `409 REPLAY_FINISHED` |
| `finished` | `pause` | `finished` | No | **Rejected**, `409 INVALID_TRANSITION` |

### 7.3 Illegal transitions are errors, never no-ops

A refused transition must return an error. A silent no-op lets a UI display
"running" while nothing advances — the precise failure mode
`PAPER_TRADING_INTEGRATION_PLAN.md:229-230` warns about.

`start` and `pause` are the exceptions the plan already declared idempotent
(`:351`, `:366`): starting an already-running replay re-arms nothing and returns
the current state. Idempotency here is about the **timer**, never about the
cursor — a repeated `start` must never reset or advance the cursor.

### 7.4 Auto-run is repeated `step()`

> **Invariant AR-1.** Auto-run is implemented as repeated invocation of the same
> `step()` used by manual stepping. There is no second code path.

A separate timing path would make results depend on scheduling, and the replay
would stop being reproducible. The timer decides **when** to step; `step()`
decides **what happens**.

### 7.5 Timer bounds

`interval_ms` default `1000`, range `100..60000` (`PAPER_TRADING_INTEGRATION_PLAN.md:346`).
Out-of-range is a validation error, never clamped — clamping would silently
change the pacing the caller asked for.

### 7.6 Finish

`finish` is not a caller action; it is a **consequence** of a step discovering
`cursor >= len(candles)`. Transition to `finished` is automatic and applies
end-of-data closure exactly once (§3.7).

---

## 8. Reset semantics

`reset()` restores the **exact** initial state. Every sub-question answered
explicitly, because each is a place where an implementation could plausibly do
the wrong thing.

| Question | Answer | Rationale |
|---|---|---|
| **Is the broker recreated?** | **Yes.** A brand-new `PaperBroker(starting_balance, costs)`. Not mutated, not zeroed, not reused. | `PAPER_TRADING_INTEGRATION_PLAN.md:205-207`. A fresh broker is also how `run_backtest` isolates every window (`walkforward.py:130`) and how `assert_no_state_carry` proves no state leaked (`walkforward.py:555-582`). |
| **Is cash restored?** | **Yes**, to `starting_balance`, by construction — a new broker initialises `cash = starting_balance` (`simulator.py:42`). | There is no "reset cash" operation, and there must not be. |
| **Is the journal cleared?** | **Yes.** A new broker has a new empty `journal` list (`simulator.py:45`). | Trade identity cannot survive a reset; a stale `PaperTrade` would be indistinguishable from a new one. |
| **Is the open position closed or removed?** | **Neither, by default — reset is refused with `409 POSITION_OPEN`.** See below. | §8.1 |
| **Is the cursor returned to the start?** | **Yes**, `cursor = start_index`, `bars_processed = 0`, `last_signal = None`. | |
| **Is `replay_id` retained or replaced?** | **Retained.** Reset is a re-run of the *same* configuration, not a new replay. | A new `replay_id` would imply a different dataset/strategy/costs, which reset does not change. The journal is empty afterwards, so there is no ambiguity about which run produced a trade. |
| **Is the strategy configuration unchanged?** | **Yes.** Held by reference and never mutated. `config_hash` is re-checked after every step and raises on drift — mirroring `walkforward.py:632-634`. | A frozen dataclass plus a hash re-check makes mid-run mutation impossible to miss. |
| **Is the dataset identity unchanged?** | **Yes.** Loaded once and cached (`marketdata.load_research_candles`, `lru_cache`). `dataset_fingerprint` is re-checked per step — mirroring `walkforward.py:644-646`. | |
| **Must reset avoid mutating the frozen dataset?** | **Yes, and it is structurally guaranteed.** Replay holds the cached candles as a `tuple` of **frozen** `Candle` dataclasses (`marketdata.py:60-77`, `models.py:6-13`). There is no mutating operation available. | The dataset is a frozen research artifact (`walkforward.DATASET_SHA256`) and Phase 10-15 hashes must remain valid. |
| **Is the dataset reloaded from disk?** | **No.** Reuse the process cache. | `PAPER_TRADING_INTEGRATION_PLAN.md:209`. Reloading would be wasteful and could in principle serve different bytes. |

### 8.1 Reset with an open position — a gap in the plan

`PAPER_TRADING_INTEGRATION_PLAN.md:205-210` specifies reset as restoring the exact
initial state but does not say what happens if a position is open. Recreating the
broker would **silently discard an open trade**.

Financially this loses nothing — the broker credits cash only on close
(`simulator.py:191`), so an open position contributes nothing to `cash`. But it
loses the *record*, and a user who pressed reset would see a position vanish with
no explanation. Worse, under the mock's mental model an open position *does*
reserve cash, so a user could reasonably expect the balance to change.

> **Recommendation R-8.1.** Refuse `reset` with `409 POSITION_OPEN` whenever
> `broker.open_trade is not None`. Require the operator to close the position
> first, or to step forward until an exit rule fires.

The alternative — force-closing at the last consumed bar with a distinct
`exit_reason` before recreating — is implementable without an engine change
(§2.3d) and preserves the audit trail, but it makes `reset` a **trading
operation**, which is precisely the category `PAPER_TRADING_ARCHITECTURE.md:477-478`
says to delete. Recorded as open question **Q2** (§26).

---

## 9. Mode architecture

Four conceptual modes. **None is implemented in this document.** The purpose
here is to make their *differences* explicit so that Phase 17F/G have a contract.

| | 🎯 Daily Target | 🧠 Manual | ⚡ High-Risk Paper | 🔔 Alerts |
|---|---|---|---|---|
| **Signal source** | `strategy.analyze` | `strategy.analyze`, surfaced only | `strategy.analyze` | `strategy.analyze` |
| **Who decides execution** | Automatic policy | **The operator**, explicitly | Automatic policy, **once qualification rules exist** | **Nobody** |
| **Automatic?** | Yes, when the target is unmet | **No** | Undefined in Phase 17 → effectively off | **Never** |
| **Own capital pool?** | Yes — its own `starting_balance` | Yes — its own | Yes — its own, explicitly separate | **No capital at all** |
| **Positions isolated?** | Yes — own broker | Yes — own broker | Yes — own broker | **No position possible** |
| **Same strategy?** | Yes, the same `StrategyConfig` | Yes | Yes (qualification may later gate *which* signals count) | Yes |
| **Executes anything?** | Paper only | Paper only | Paper only | **No. Never.** |

### 9.1 Invariants common to every mode

- **M-1.** All four are **paper/research** modes. No real money, no exchange
  connectivity, no order submission, no leverage, no margin, ever.
- **M-2.** Every executing mode owns a **separate `PaperBroker`**. Capital is
  never shared (§11).
- **M-3.** Alerts hold **no broker reference at all** — see §19.
- **M-4.** No mode may reimplement signal generation, sizing, fills or costs. All
  of that stays in `strategy.analyze` and `PaperBroker`.
- **M-5.** No mode may weaken ALI-1. A mode policy decides *whether* to act on a
  signal; it can never let the strategy see further into the future.

### 9.2 The strategy is shared, the *policy* is not

All modes call the same `analyze` with the same `StrategyConfig`. They differ
only in the execution policy object (§6). This is what makes mode isolation a
capital problem rather than a strategy problem — and it is why no mode needs a
variant of the strategy, which would be a research change.

---

## 10. 🎯 Daily Target mode — contract only

**Not implemented.** This is the contract a later phase must satisfy.

| Aspect | Contract |
|---|---|
| **Paper starting allocation** | Its own `starting_balance`, an explicit parameter. Must be `> 0` — `PaperBroker.__init__` raises otherwise (`simulator.py:38-39`). Not carved out of a shared pool (§11). |
| **Profit target** | A threshold on **realized net P&L** — i.e. `broker.cash - broker.starting_balance`, the engine's own `BacktestResult.net_pnl` definition (`results.py:21-22`) and already exposed as `/api/account.realized_pnl`. |
| **Optional loss limit** | Symmetric threshold on the same quantity: `realized_pnl <= -limit`. Needs no engine support — it is a comparison on an existing value. |
| **When evaluated** | After any step in which a trade **closed**, i.e. when `broker.cash` changed. Checking after every step regardless is harmless but wasteful; checking only on close is the honest reading of "realized". |
| **On target crossed** | Stop this mode's **auto-run** and stop opening new positions. Other modes are unaffected (§11). |
| **Does the session stop?** | **Only this mode's replay.** A Daily target must not pause Manual or High-Risk. |
| **Is an open position closed?** | **Recommended: no.** Let it exit by the engine's own rules. Force-closing on target would be a trading operation (§14) and would also change the very P&L being measured. Recorded as **Q4**. |
| **Overshoot** | **Guaranteed possible and unbounded.** See below. |
| **Execution timing effect** | Exits fill at the **next** bar's **open** (`backtest.py:185`). Realized P&L therefore jumps **discretely**, by the full net P&L of a whole trade, at one step. The target is never approached continuously. |

### 10.1 The target cannot be hit exactly — stated as a design property

> **The Daily Target is an approximation and the architecture must say so out
> loud.**

Because realized P&L only changes when a trade closes, and a trade's net P&L is
whatever the next bar's open produced, the realized value **steps past** the
target rather than landing on it. A target of +50 with a single trade closing at
+180 overshoots by +130. There is no partial close in the engine, no scaling out,
and no mechanism to stop at a threshold. Adding one would require a new exit rule
— a **strategy/execution change** that must go through a research phase with its
own pre-registration.

Any UI must therefore present the target as a *goal that may be overshot*, never
as a guarantee. Recorded as **Q5**.

---

## 11. ⚡ High-Risk Paper mode — architecture only

**Not implemented.** Deliberately under-specified.

| Aspect | Contract |
|---|---|
| **Capital** | Its own allocation, separate from Daily and Manual. Named "high risk" because of the *user-chosen* allocation and any future qualification rules — **not** because of leverage. |
| **Leverage / margin** | **Prohibited.** The engine has no margin concept; adding one would be a new accounting implementation. |
| **Automatic execution** | Only after a future phase defines **qualification rules**. Until then, High-Risk produces signals and takes **no** automatic action. |
| **Qualification rules** | **Deliberately not invented here.** Candidates exist (larger size, wider stops, only strong breakouts) but each is a research question with real P&L consequences, and inventing one here would smuggle an untested strategy variant into a UI phase. Recorded as **Q6**. |
| **Isolation** | Own broker, own position, own journal (§12). |
| **Real money** | **None.** No exchange connectivity exists or will be added. |

---

## 12. 🔔 Alerts mode — notification only

**Not implemented.** The rule is absolute and architectural:

```
SIGNAL  ──▶  ALERT          (a notification)
       ╳
       ──▶  ORDER / FILL    (never)
```

> **Invariant AL-1.** An alert **never** opens, closes, or modifies a position,
> and never causes any broker method to be called.

### 12.1 Structural enforcement, not just intent

The strongest guarantee is that the alerts component **holds no broker reference
at all**. If the object that formats a notification cannot reach a
`PaperBroker`, it is *incapable* of executing, rather than merely instructed not
to. This is testable: assert that the alerts module has no `PaperBroker` import
and no reference to `open_from_signal` / `close` — the same AST-based approach
Phase 16 used for its engine-import allowlist
(`tests/test_api_health.py:ALLOWED_ENGINE_IMPORTS`).

### 12.2 Why this matters

Alert-driven execution is the single most likely route by which a "paper" tool
quietly becomes a trading tool: a notification fires, something acts, and no
human decision was ever made. Keeping alerts structurally incapable of execution
means that route does not exist.

---

## 13. Capital isolation

### 13.1 Options considered

| Option | Assessment |
|---|---|
| **Separate `PaperBroker` per mode** | **Chosen.** Zero engine change. Matches the engine's existing "fresh broker per independent run" pattern (`backtest.py:130`, one broker per call; `walkforward.py:19-20`, "every window gets a fresh account"). Isolation is structural: separate `cash`, separate `journal`, separate `open_trade`. |
| One shared broker + a mode tag on each trade | **Rejected.** Requires adding a field to `PaperTrade` (an engine model change) *and* a new filtered-balance computation — i.e. new accounting, which is the exact duplication the architecture forbids (`PAPER_TRADING_ARCHITECTURE.md:254`). Per-mode balance would then be derived rather than authoritative. |
| Subclass `PaperBroker` per mode | **Rejected.** Produces a second implementation of the same accounting. The moment it diverges, there are two sources of truth. |
| One broker with partitioned cash | **Rejected.** Invents margin/partition semantics the engine explicitly lacks, and reintroduces the cash-reservation model the audit flagged for deletion (`PAPER_TRADING_ARCHITECTURE.md:33-36`). |

### 13.2 Decision

> **Separate `PaperBroker` instances, one per mode, owned by a session registry
> that dispatches by mode key.**

The registry is a thin container — a mapping of mode key → `(broker, replay)` —
and holds **no accounting of its own**. Every figure comes from the selected
broker. This mirrors `paper_api.session.PaperSession`, which already wraps one
broker and computes only `balance - starting_balance`.

### 13.3 Consequence: the single-position invariant becomes per-mode

The engine's one-at-a-time rule is enforced *per broker*
(`simulator.py:79-80`). With three independent brokers, the session may hold **up
to three concurrent paper positions** — one per mode.

This is a deliberate, documented relaxation and must be stated in the UI. It is
**not** a bug and **not** the mock's "multiple concurrent positions" defect
(`PAPER_TRADING_ARCHITECTURE.md:39-40`): that defect was *unbounded* concurrency
inside one accounting model. Here, concurrency is bounded by the number of modes
and each position is independently accounted.

### 13.4 Identity

Each mode's replay carries its own `mode` key and its own dataset/strategy/
execution identity. The strategy identity is **identical** across modes (§9.2);
the execution identity may differ per mode if a mode is given different costs.
That is a deliberate choice — and a recorded risk, since it makes cross-mode
comparison of P&L less like-for-like. Recorded as **Q7**.

---

## 14. Close position / close all — architecture only

**Not implemented, and currently contested.** The Phase 17 brief requires this
architecture; an existing planning document forbids the feature. The conflict is
stated rather than resolved.

### 14.1 The conflict

`PAPER_TRADING_INTEGRATION_PLAN.md:391` **rejects** `POST /api/position/close`:

> `POST /api/position/close` | Manual close is a trading control and breaks the
> 2.3 invariant

and `PAPER_TRADING_ARCHITECTURE.md:477-478, 555`:

> that component is **removed**, not adapted — a manual close is a real trading
> control regardless of whether money is involved.

The invariant referred to (`PAPER_TRADING_INTEGRATION_PLAN.md:132-140`) is:

> If every trade originates from `PaperBroker.open_from_signal(signal)` where
> `signal` came from `strategy.analyze`, then the trades the application shows
> are a subset of the trades the research engine could have produced.

**Precise reading of the conflict.** A manual close does not violate the
*origination* clause — the position still originated from `analyze` via
`open_from_signal`. What it breaks is the *subset* clause: closing early produces
a trade the engine, given the same historical data, would **not** have produced,
because it would have held the position longer.

So the invariant as written is **stronger than its own rationale requires**, and
the rationale ("any UI-side shortcut breaks this immediately") over-reaches to
the closing side. That is an argument, not a licence — the invariant is a
deliberate safety property and its author may have intended the strict reading.
Recorded as **Q1**, the most consequential open question in this document.

### 14.2 Architecture, if the feature is approved

**Authoritative operation:** `PaperBroker.close(price, timestamp)`
(`simulator.py:118`). Not a new method, not a wrapper that computes P&L. Replay
supplies the price and timestamp; the broker does everything else.

**Fill price in replay.** The only defensible price is one the replay model
already contains. Options, in preference order:

1. **The next unconsumed candle's open** (`candles[cursor].open`) — exactly the
   price a rule-triggered exit would use. Consistent with every engine exit
   (`backtest.py:185`).
2. The last consumed candle's close — the price end-of-data uses
   (`backtest.py:210`), but that bar is already "spent".

**Never** the signal's `price`, never a client-supplied price, never an
interpolated or synthetic value. There is no live market to ask.

**Costs.** The broker applies them. Nothing extra: `close()` sets `fee_total`,
then either `spread_total`/`slippage_total`/`costs` per the execution model
(`simulator.py:164-189`), credits `cash += net_pnl` (`:191`), appends to the
journal (`:193`) and clears `open_trade` (`:194`). Replay sets `exit_reason` and
`bars_held` afterwards, because the broker does not (§2.3c).

**Journal.** Appended by `close()` itself. No separate write, no shadow ledger.

**If no position is open.** `close()` raises
`ValueError("no paper trade is open")` (`simulator.py:123-124`). The API maps
this to `409 NO_POSITION`. It must **not** be a silent success — "close all" with
nothing open should report per-mode outcomes, not an unqualified 200.

**With multiple mode sessions.** Close is dispatched to **exactly one** broker,
selected by mode. There is no cross-broker operation (§15).

**`exit_reason` label.** A distinct value such as `"operator_close"` is required
so that operator-initiated exits are distinguishable in the journal and in
`exit_counts`. Because `models.py:75` declares `exit_reason` as an unconstrained
`str` (§2.3d), this needs **no engine change** — but it does mean `exit_reason`
becomes an open enumeration in practice, which existing consumers must tolerate.
Note `BacktestResult.exit_counts` (`results.py:14`) is a `dict[str, int]`, so a
new key flows through without schema change.

### 14.3 Recommendation

Do **not** expose close endpoints in Phase 17. The invariant conflict needs an
explicit decision (Q1) before code exists, and an endpoint cannot be added
later "temporarily" without becoming permanent. Revisit in a dedicated phase with
either the invariant amended (entry-origination-only) or the feature declined.

---

## 15. Mode-specific close all

**Not implemented.**

| Question | Answer |
|---|---|
| Separate broker operations, or filtered journal operations? | **Separate broker operations.** Closing is a **mutation of broker state**, so it must be performed by the broker that owns the position. Filtering a shared journal would require the shared-broker design rejected in §13.1. |
| Where does the iteration live? | The session registry iterates its mode map and calls `close()` on each broker that has an open trade. The registry **dispatches**; it never computes a price or a P&L. |
| How is cross-mode contamination prevented? | Structurally. Mode A's close call is `brokers["daily"].close(...)`. There is no code path by which one mode's operation touches another mode's broker, because each broker is a separate object with a separate journal. |
| What does "close all" report? | A per-mode outcome: `{daily: closed, manual: no_position, high_risk: closed}`. Not a single boolean — a blanket success would hide the fact that one mode did nothing. |
| What if a mode's broker has no position? | `409 NO_POSITION` for that mode. Not an error for the request as a whole. |

### 15.1 The guarantee that matters

> A close request naming mode `X` can only ever affect mode `X`'s broker.

This must be **testable**: a test that opens positions in two modes, closes all in
one, and asserts the other's `open_trade`, `cash` and `journal` are byte-identical
before and after. Without such a test, a future refactor to a shared broker could
introduce cross-mode contamination silently.

---

## 16. Signal versus execution

### 16.1 The separation

> **A `Signal` is an observation. It is not an order, a fill, a position, or a
> commitment.**

`analyze` returns `side ∈ {long, short, flat}` with a `reason` string and no side
effect (`strategy.py:49-212`). Whether that observation becomes a simulated trade
is a **policy decision** made outside the strategy. In `run_backtest` that policy
is hard-coded at `backtest.py:195-205`; in replay it must be an explicit,
mode-selectable object (§6).

### 16.2 `flat` never trades

`open_from_signal` rejects `flat` outright (`simulator.py:76-77`). A flat signal
is a normal, frequent outcome — the default branch of `analyze`
(`strategy.py:191-192`) — and must never be surfaced as an error.

### 16.3 Who controls signal → execution, per mode

| Mode | Controller | Automatic? | Gate conditions |
|---|---|---|---|
| 🎯 Daily Target | Automatic policy | Yes | Target not met · no open position · `_side_allowed` · `index >= evaluation_start` · target not already satisfied |
| 🧠 Manual | **The operator** | **No** | An explicit human action. Without it, no trade — ever. |
| ⚡ High-Risk | Automatic policy | **Undefined** | Qualification rules do not exist yet (Q6) → no automatic execution in Phase 17 |
| 🔔 Alerts | **Nobody** | **Never** | No broker reference exists (§12.1) |

### 16.4 Why this matters most for Manual and Alerts

These two modes exist **because** signal and execution are separable. If the
replay layer fused them — calling `open_from_signal` inline the way
`run_backtest` does — then:

- **Manual** would be unimplementable, because "show me the signal but do not
  trade it" would be inexpressible.
- **Alerts** would be indistinguishable from an auto-trading mode, and the
  `SIGNAL → ALERT` rule of §12 would be enforced only by convention.

This is the single strongest architectural argument for the explicit-policy
design in §6.

---

## 17. Determinism and concurrency

### 17.1 Determinism requirements

| Requirement | Statement |
|---|---|
| **D-1** | `step()` is a pure function of `(cursor, broker state, dataset, config, costs)`. No wall clock, no randomness, no I/O beyond the already-loaded array. |
| **D-2** | Stepping twice from the same cursor yields identical results. No hidden timer state. |
| **D-3** | Auto-run is repeated `step()` (§7.4), so pacing cannot affect outcomes. |
| **D-4** | Identical responses across repeated calls — the property Phase 16 already tests per endpoint. |
| **D-5** | Replay over `N` steps equals the `run_backtest` prefix at the same point (§4.4 T4). |

### 17.2 Concurrency: the minimum for a local single-user tool

No database. No distributed lock. No queue. One process, one user, loopback only.

| Hazard | Required protection |
|---|---|
| **Two clients calling `step()` concurrently** | **A single re-entrant lock (`threading.RLock`) around every mutating replay operation.** This is not theoretical: FastAPI executes non-async `def` endpoints in a threadpool, so two requests genuinely can interleave. Without a lock, two steps could interleave between the cursor read and the cursor write and corrupt `entry_index`/`bars_held`. |
| **`reset` during `running`** | The same lock, plus: reset stops the timer **before** recreating the broker. A reset must never race the timer thread. |
| **Two clients requesting close simultaneously** | The same lock. `PaperBroker.close` raises if no trade is open, so the second call must surface `409 NO_POSITION` rather than corrupt state. |
| **Repeated identical `step()`** | Not idempotent by design — a step *advances*. A client retrying after a timeout will advance twice. Mitigation: the response carries the resulting `cursor`, and the client compares. Deliberately **not** made idempotent via a request key; that would add state for a single-user tool. |
| **Repeated `start` / `pause`** | Idempotent on the **timer** only (§7.3). Never resets or advances the cursor. |
| **Stale UI state** | Out of scope for the server. The client already fetches a snapshot; the `cursor` in each response is the authoritative reconciliation point. |

### 17.3 Why not more

A single `RLock` is sufficient because there is exactly one mutating actor (the
user, via their browser) and one process. Adding a database or a distributed lock
would introduce failure modes — partial writes, migration, auth — in exchange for
solving a problem that cannot occur under the documented deployment.

---

## 18. Persistence

### 18.1 Decision: none in Phase 17

> **Replay state is process-local. It is not persisted, and Phase 17 requires no
> persistence.**

### 18.2 Consequences, stated plainly

| Event | Result |
|---|---|
| **API restart** | All replay state lost. Cursor returns to `start_index`, broker recreated empty. |
| **Replay restart** | Identical to the above — the process *is* the replay's lifetime. |
| **Browser refresh** | **No effect.** State lives server-side; the client re-fetches the snapshot. |
| **Session recovery** | **Not supported.** Not deferred-and-promised — declined. |

### 18.3 Why this is acceptable

1. **Replay is reproducible from scratch.** Given the same frozen dataset,
   strategy and execution identity, a replay from `start_index` is
   deterministic (§17.1). Persistence would save *time*, not *data* — the
   expensive artefact (the dataset) is already on disk and hash-verified.
2. **Resuming mid-position is not supported by the engine.** `PaperBroker` has no
   `from_state` constructor and `PaperTrade` has no serialisation contract.
   Persistence would therefore require inventing a broker snapshot format — a new
   authoritative representation of engine state, which is precisely what Phase 16
   was built to avoid.
3. **Single-user, educational, local.** The integration plan already flagged
   persistence as out of scope for the teaching tool
   (`PAPER_TRADING_INTEGRATION_PLAN.md:1069-1072`).

### 18.4 If it is ever needed

The smallest defensible option is a full-session JSON snapshot written on every
mutation and reloaded on startup, including `cursor`, `entry_index`, `start_index`,
`status`, and the full broker (`cash`, `open_trade`, `journal`). It must include
the dataset/strategy/execution identities and **refuse to resume** if any of them
differs from the loaded configuration. A resume with an open position is the hard
case and needs its own design phase.

---

## 19. Dataset identity

Replay must state exactly which historical dataset it is walking. Reuse the
existing frozen constants — **do not** create a second identity system.

| Field | Source | Value |
|---|---|---|
| `asset` | `config.asset` | `BTC/USDT` |
| `timeframe` | `config.timeframe` | `1h` |
| `dataset_sha256` | `walkforward.DATASET_SHA256` via `marketdata.dataset_identity()` | `201A3B15…16B` |
| `first_timestamp` | `walkforward.DATASET_FIRST` | `2024-01-01 00:00` UTC |
| `last_timestamp` | `walkforward.DATASET_LAST` | `2025-12-31 23:00` UTC |
| `candle_count` | `walkforward.DATASET_CANDLES` | `17,544` |
| `interval_seconds` | `walkforward.EXPECTED_INTERVAL_SECONDS` | `3600` |

**Filesystem paths must not be exposed.** `marketdata.dataset_path()` exists for
internal resolution against the package location
(`marketdata.py:39`, `:54-57`) and the Phase 16C route already asserts that no
path appears in any payload. `SOURCE_LABEL = "local-research-dataset"`
(`marketdata.py:51`) is the provenance string; a hash is an identity, not a path.

**Integrity is verified before use, not assumed.** `load_research_candles()`
already runs `validate_dataset_integrity` — hash, bounds, count, strict ordering,
exact spacing — once per process (`marketdata.py:60-77`). Replay reuses that
cached tuple; it must not add a second loader. A dataset that fails validation is
not replayed, exactly as it is not served.

**Mid-run mutation guard.** `dataset_fingerprint(candles)` is re-checked after
every step and raises on change, mirroring `walkforward.py:644-646`. Structurally
unnecessary for a frozen tuple of frozen dataclasses, but it is cheap and it makes
the invariant explicit.

---

## 20. Strategy and execution identity

### 20.1 Strategy

Reuse `walkforward.config_hash` (`walkforward.py:424-427`), which is
`sha256(repr(config))` — the **same** mechanism Phase 13 froze and Phase 16
already serves as `config_hash` / `config_repr`. **Do not create another
configuration identity system.** A second hash function would make two
configurations with different hashes but identical behaviour look different, and
vice versa.

Frozen baseline identity:

```
config_hash = 2FBDB9A8814ABC81062C2B0A61DFDCFAC69C95CF1789D0BAE6BEE4B11ADC3BF7
```

### 20.2 Execution

Reuse `walkforward.costs_hash` (`walkforward.py:430-433`) plus `repr(costs)`:

| Field | Frozen value |
|---|---|
| `execution_model` | `cost_deduction` |
| `fee_rate` | `0.001` |
| `slippage_rate` | `0.0005` |
| `spread_rate` | `0.0` |
| `costs_hash` | `C24F79986249A05541709B583015FFBE012055DC324F4C4F6ED8CF97B6123C7E` |
| `risk_fraction` | `0.01` |

Constructed via `walkforward.phase13_costs()`, which returns a **fresh** value on
every call so a caller cannot mutate shared state (`walkforward.py:81-91`).

Both hashes are re-checked after every step, mirroring
`walkforward.py:632-638`. A mid-run change raises rather than producing a run
whose halves used different assumptions.

---

## 21. Error model

Not implemented. Codes align with `PAPER_TRADING_INTEGRATION_PLAN.md` where it
already defines them; divergences are marked.

| Condition | HTTP | Code | Notes |
|---|---|---|---|
| Unknown `replay_id` | `404` | `REPLAY_NOT_FOUND` | |
| `step` while `finished` | `409` | `REPLAY_FINISHED` | Plan §4.2. **Not** a silent no-op. |
| `start` while `finished` | `409` | `REPLAY_FINISHED` | |
| `pause` while `idle`/`finished` | `409` | `INVALID_TRANSITION` | |
| `step` with no execution bar but not yet `finished` | `409` | `INVALID_TRANSITION` | Defensive; should be unreachable. |
| `reset` with an open position | `409` | `POSITION_OPEN` | Recommendation R-8.1 (Q2). |
| Close with no open position | `409` | `NO_POSITION` | Per mode. |
| `count` outside `1..5000` | `400` | `INVALID_COUNT` | Plan §4.2 uses `400`. |
| `interval_ms` outside `100..60000` | `400` | `INVALID_INTERVAL` | Plan §4.2 uses `400`. |
| `start_index` below `minimum_history` | `422` | `INSUFFICIENT_HISTORY` | Surfaces explicitly instead of leaking `analyze`'s generic `ValueError` (`strategy.py:55-57`). Plan §3.5 requires this. |
| `at` is not a candle timestamp | `404` | `UNKNOWN_TIMESTAMP` | Matches Phase 16D. Exact match only; never interpolated. |
| Unknown `mode` key | `422` | `INVALID_MODE` | |
| Dataset missing or failing integrity | `503` | `NO_DATA` | Plan §4.2. |
| Engine/broker unexpectedly unavailable | `503` | `ENGINE_UNAVAILABLE` | Plan §4.2. |
| `reset` requested in an impossible state | `409` | `INVALID_TRANSITION` | |

### 21.1 Divergence from the plan, flagged

The plan specifies `400` for `INVALID_COUNT` / `INVALID_INTERVAL`. FastAPI's own
validation failures use `422`. Both are defensible; mixing them within one API is
not. Recommendation: use `422` for semantically-invalid-but-well-formed values
and reserve `400` for malformed requests, and change the plan's two codes when
the endpoints are written. **Not changed here** — this document does not modify
the plan. Recorded as **Q9**.

### 21.2 Errors are not silently swallowed

A refused transition must never return `200`. A UI that receives `200` from
`step()` while `finished` would display progress that did not happen.

---

## 22. API contract plan

**No endpoints are defined here.** This is a plan, with justification per route.

### 22.1 Deliberate deviation: no `GET /api/replay`

`PAPER_TRADING_INTEGRATION_PLAN.md:339-341` and §4.9 argue for a **single
aggregate snapshot**: "One object so the dashboard needs one fetch and cannot
interleave inconsistent states across panels." A separate `GET /api/replay`
reintroduces exactly the two-fetch interleaving problem §4.9 exists to prevent.

> **Recommendation R-22.1.** Fold replay state into `/api/session` as the
> aggregate snapshot §4.9 describes. Do **not** add `GET /api/replay`.

**Cost of this recommendation, stated honestly:** Phase 16 shipped
`SessionResponse` with `state: Literal["idle"]`, `active: bool` and
`open_position: None` as deliberate, tested constraints. Extending it to carry
replay state **widens a shipped contract** and requires updating the Phase 16
route-scope and schema tests. That is a real cost, and it is the reason this is
flagged as **Q3** rather than simply decided. The alternative — a separate
endpoint — preserves the Phase 16 contract but accepts the interleaving risk.

### 22.2 Planned endpoints

| Method | Path | Mutates | Request | Response | Transition | Justification |
|---|---|---|---|---|---|---|
| `POST` | `/api/replay` | **yes** | `{ start_index?, mode? }` | replay snapshot | — → `idle` | Create. Necessary: replay must be creatable with a walk-forward boundary (§3.8) and a mode (§13). |
| `POST` | `/api/replay/start` | **yes** | `{ interval_ms? }` | `{ status, cursor }` | `idle\|paused` → `running` | Auto-run. Idempotent on the timer. |
| `POST` | `/api/replay/pause` | **yes** | none | `{ status, cursor }` | `running` → `paused` | Counterpart to start. Not a trading control — it only stops the cursor advancing. |
| `POST` | `/api/replay/step` | **yes** | `{ count? }` (1..5000, default 1) | full snapshot + `steps_executed` | any but `finished` | Deterministic manual advance. `count > 1` is justified: one-candle stepping to a region of interest is unusable, and N calls is still literally N calls to the same path (§7.4). |
| `POST` | `/api/replay/reset` | **yes** | none | initial snapshot | any → `idle` | Reproducible re-run (§8). |
| `GET` | `/api/session` | no | — | **extended** aggregate | — | Per R-22.1. See Q3. |

**Not planned:** any `close`, `open`, `order`, `execute`, `seek` or mode-management
endpoint. `seek` is excluded because backwards movement is equivalent to
`reset` + `step(count)` and is therefore deterministically derivable
(`PAPER_TRADING_INTEGRATION_PLAN.md:393`). Close endpoints are blocked on Q1.

### 22.3 Conventions inherited from Phase 16

- JSON only; `Content-Type: application/json`.
- Timestamps ISO-8601 **with offset**, via `marketdata.as_utc`. Never naive
  (`marketdata.py:101-113`).
- Floats at full precision; **no rounding in Python** (`PLAN:4.4`).
- `null` for "not applicable", never `0`, never `""` — the Phase 14B convention.
- `Literal` types wherever the engine is closed (`mode: "paper"`, `status` enum).
- No filesystem paths, no environment values, no credentials.
- Loopback bind only (`config.LOOPBACK_HOSTS`); no CORS middleware.

### 22.4 Validation summary

| Input | Rule | Error |
|---|---|---|
| `start_index` | `>= minimum_history(config)` and `< len(candles)` | `422 INSUFFICIENT_HISTORY` |
| `count` | `1 <= count <= 5000` | `400/422 INVALID_COUNT` (Q9) |
| `interval_ms` | `100 <= interval_ms <= 60000` | `400/422 INVALID_INTERVAL` (Q9) |
| `mode` | Known registry key | `422 INVALID_MODE` |

---

## 23. Test plan

Tests Phase 17 must pass. Grouped by the guarantee they defend. Fixtures must be
**engine-produced**: real `analyze` calls driving a real `PaperBroker`. No
hand-built `PaperTrade` — the Phase 16E lesson was that hand-built fixtures let
tests assert against fields the engine never populates.

### 23.1 Causality and determinism

| # | Test | Defends |
|---|---|---|
| 1 | Signal invariance under mutation of all candles `>= i` | ALI-1 |
| 2 | Mutating `candles[i]` changes the fill but not the signal | ALI-2 |
| 3 | Mutating all candles `> N` leaves state after N steps identical | ALI-3 |
| 4 | **Replay prefix ≡ `run_backtest` prefix, for every cursor** | D-5, §4.4 T4 |
| 5 | Two `step()` calls from the same cursor give identical state | D-2 |
| 6 | Identical bytes across repeated snapshot requests | D-4 |
| 7 | Auto-run produces exactly the same state as manual stepping | D-3, AR-1 |

### 23.2 Execution semantics

| # | Test | Defends |
|---|---|---|
| 8 | Fill price equals `candles[i].open`, never `.close` | §2.2 |
| 9 | Signal bar is `candles[i-1]`; one-bar gap always | §4.2 |
| 10 | `fee_total == (entry_value + exit_value) * fee_rate` | `simulator.py:160-162` |
| 11 | Under `cost_deduction`: `costs == fee_total + slippage_total`, `spread_total == 0` | `simulator.py:180-189` |
| 12 | Under `fill_price`: `costs == fee_total`, spread/slippage attributed not deducted | `simulator.py:164-179` |
| 13 | `quantity == (cash * risk_fraction) / fill` | `simulator.py:92` |
| 14 | Cash is **not** reserved at entry; unchanged while open | `simulator.py:191` |
| 15 | Long P&L sign and short P&L sign are mirrored | `models.py:122` |
| 16 | A second entry is refused while a position is open | `simulator.py:79-80` |
| 17 | `flat` signal produces no trade and no error | `simulator.py:76-77` |

### 23.3 Exit rules

| # | Test | Defends |
|---|---|---|
| 18 | Exit rules do **not** fire on the entry bar (`bars_held < 1`) | `backtest.py:158` |
| 19 | `max_holding_bars` fires at exactly `bars_held == max_holding_bars` | `backtest.py:161-165` |
| 20 | Stop detected on `candles[i-1]`, filled at `candles[i].open` | `backtest.py:159`, `:185` |
| 21 | Take-profit likewise | `backtest.py:170-174` |
| 22 | Stop and target on one bar → `stop_loss` wins | `backtest.py:170-172` |
| 23 | Stop/target anchored to `entry_price`, not the raw reference | `backtest.py:38-42` |
| 24 | Opposite-signal exit fires only when no optional rule already did | `backtest.py:177-181` |
| 25 | Reversal: one step closes **and** opens at the same open; count over the full dataset and assert **343 of 344** trades participate | §2.3a, §3.4 |
| 26 | End-of-data closes at the final candle's **close** | `backtest.py:210` |
| 27 | `end_of_data` reachable with `bars_held == 0` (same-bar open+close at the final bar) — **permitted by the code, absent from the frozen baseline**, so the fixture must construct the case deliberately | §2.3b |
| 28 | `exit_reason` and `bars_held` are written by replay after `close()` | §2.3c |

### 23.4 Lifecycle

| # | Test | Defends |
|---|---|---|
| 29 | State machine allows exactly the transitions in §7.2 | §7.2 |
| 30 | Every illegal transition returns an error, never `200` | §7.3 |
| 31 | `start` twice does not reset or advance the cursor | §7.3 |
| 32 | `step` from `finished` → `409 REPLAY_FINISHED` | §3.7 |
| 33 | Reset from `finished` returns to `idle` and is the only exit | §7.2 |
| 34 | `interval_ms` out of range is rejected, not clamped | §7.5 |

### 23.5 Reset

| # | Test | Defends |
|---|---|---|
| 35 | Reset restores cash, empties journal, clears position, rewinds cursor | §8 |
| 36 | Reset retains `replay_id`; config and costs unchanged | §8 |
| 37 | Reset then N steps reproduces the first run exactly | §8, D-5 |
| 38 | Reset with an open position → `409 POSITION_OPEN` | R-8.1 |
| 39 | The frozen dataset is byte-identical after any reset/step sequence | §8 |

### 23.6 Modes

| # | Test | Defends |
|---|---|---|
| 40 | Manual: a long signal produces **no** trade without an operator action | §16.3 |
| 41 | Alerts: signal produces a notification and **zero** broker mutations | §12 |
| 42 | Alerts module has no `PaperBroker` import (AST) | §12.1 |
| 43 | Daily Target stops opening positions once the target is met | §10 |
| 44 | Daily Target does not stop other modes | §10, M-2 |
| 45 | High-Risk takes no automatic action while qualification is undefined | §11 |
| 46 | Closing all in mode A leaves mode B's position, cash and journal identical | §15.1 |
| 47 | Per-mode cash never mixes; each broker's `starting_balance` is its own | §13 |

### 23.7 Identity

| # | Test | Defends |
|---|---|---|
| 48 | Dataset identity fields match the frozen constants | §19 |
| 49 | `config_hash` matches the frozen baseline hash | §20.1 |
| 50 | `costs_hash` matches the frozen costs hash | §20.2 |
| 51 | Mid-run mutation of config, costs or dataset raises | §19, §20.2 |
| 52 | No filesystem path appears in any replay payload | §19, Phase 16C precedent |

### 23.8 Mutation-testing opportunities

Each of these is a single-token change that a correct suite must kill:

| Mutation | Killed by |
|---|---|
| `candles[:i]` → `candles[:i+1]` (introduces lookahead) | Test 1, 2 |
| `candles[:i]` → `candles[:i+2]` | Test 1, 2 |
| `execution_bar.open` → `execution_bar.close` | Test 8 |
| `closed_bar = candles[i-1]` → `candles[i]` | Test 20 |
| remove `bars_held >= 1` guard | Test 18 |
| swap exit block and entry block | Test 25 |
| `max_holding` precedence below stop/target | Test 19, 22 |
| `last.close` → `last.open` at end-of-data | Test 26 |
| `quantity = (cash*r)/fill` → `* fill` | Test 13 |
| deduct spread **and** slippage under `fill_price` | Test 12 |
| `cursor = i` → `cursor = i + 1` (skips a bar) | Test 4, 9 |
| omit `last_signal` update | Test 6 |
| `_side_allowed` applied to exits instead of entries | New test required |
| `starting_balance` read from a constant, not the broker | Test 47 |

The Phase 14 precedent is a harness that runs N single-token mutants and requires
all to be caught; the Phase 17 suite should adopt the same shape.

---

## 24. Research safety

Standing constraints. They are properties of the product, not disclaimers.

| # | Constraint |
|---|---|
| **S-1** | **Replay does not prove future profitability.** It walks candles that have already occurred. |
| **S-2** | **Historical results are not predictions.** The Phase 13 record already reports negative findings — baseline net −157.14 over 344 trades, profit factor 0.6920, every confidence interval containing zero — and the largest single win is **+378.8%** of net P&L (`RESEARCH_CHECKPOINT.md:81`, `:151`). Extreme concentration means a single trade dominates the result. |
| **S-3** | **Paper results are simulated.** Fills are assumed at bar opens. No venue, no order book, no queue position, no partial fills. |
| **S-4** | **No real money is involved.** Every balance is simulated. No wallet, deposit, withdrawal or transfer concept exists. |
| **S-5** | **No exchange orders are submitted.** No connectivity, no credentials, no venue adapter. `MARKET_DATA_API_KEY` is for a future *public* data provider and is deliberately unconsumed (`config.py:4-6`). |
| **S-6** | **No leverage or margin.** The engine has no margin concept; `reserved_capital` is absent, not zero. |
| **S-7** | **No live or future data.** Replay cannot read a candle it has not reached. ALI-1 enforces this. |
| **S-8** | **The strategy is unmodified.** Replay changes no gate, no indicator, no sizing, no cost. Test 4 is the regression guard. |
| **S-9** | **The research record is frozen.** Phase 10-15 artifacts and both datasets remain byte-identical; replay reads them and never writes them. |
| **S-10** | **The four conceptual modes are paper/research modes.** "High-Risk" denotes a user-chosen allocation, never leverage or real capital. |

---

## 25. Implementation order

Chosen after inspecting the engine, and **not** the order sketched in the Phase 17
brief. Two deliberate reorderings, both explained.

| Phase | Scope | Rationale for position |
|---|---|---|
| **17B** | **Replay state model and the deterministic step.** `ReplayState`, `step()`, cursor, `entry_index`, ALI-1/2/3 tests, and **backtest-prefix equivalence**. | First, because it is the only component that must be *provably identical* to the research engine. Everything else depends on it, and equivalence is cheapest to prove before any other concern is layered on. |
| **17C** | **Lifecycle.** `idle/running/paused/finished`, start/pause, end-of-data finish, the error model. Still no HTTP. | Second: the state machine is pure Python and fully testable without a transport. Doing it before HTTP keeps the transport a thin shell. |
| **17D** | **Transport.** The replay endpoints, `/api/session` extension, the `RLock`, validation. | Third: a thin shell over proven logic. The one thing that must not happen is logic leaking into route handlers, which is why `/api/session` stays a projection. |
| **17E** | **Signal/execution separation.** The explicit policy object (§6), plus proof that `analyze` has no side effects and that Manual produces no trade without an action. | Fourth: the policy seam must exist **before** any mode exists, or the first mode will hard-code it and Manual becomes unimplementable. |
| **17F** | **Mode registry and capital isolation.** Separate brokers per mode, dispatch by key, isolation tests. | Fifth — **moved earlier than the brief suggested.** Establishing isolation *before* per-mode policies means each policy is written against an already-isolated broker. Retrofitting isolation after three modes each own a broker is materially harder. |
| **17G** | **Daily Target / High-Risk / Alerts contracts.** Each explicitly gated; Alerts structurally incapable of execution. | Sixth: depends on 17E and 17F. High-Risk ships **disabled** pending Q6. |
| **17H** | **Close controls.** | **BLOCKED** — not scheduled. Requires an explicit decision on Q1. Deliberately placed after every other capability, so that declining it costs nothing and so that no close endpoint exists anywhere near a shipped phase. |
| **17I** | **Dashboard integration.** Replace the mock's engine, signal and accounting layers with a thin read-only client of the Python session. | Last: it is presentation, and it is worthless until the engine beneath it is right. The audit's four divergences (`PAPER_TRADING_ARCHITECTURE.md:24-41`) all get deleted here — not adapted. |

**Not scheduled:** persistence (§18, declined), mode-management endpoints (§22.2),
`seek` (§22.2, derivable), any live-data capability (§1.3, permanently out).

---

## 26. Open questions and ambiguities

Recorded rather than silently decided. **Q1 and Q2 block implementation.**

### Q1 — Manual close vs the §2.3 invariant *(blocking, needs sign-off)*

`PAPER_TRADING_INTEGRATION_PLAN.md:391` rejects `POST /api/position/close` as a
trading control that breaks the invariant at `:132-140`, and
`PAPER_TRADING_ARCHITECTURE.md:477-478, 555` says to delete it. The Phase 17 brief
requires its architecture (§14, §15).

My reading is that the invariant's *origination* clause is not violated by a
close, but its *subset* clause is — closing early produces a trade the engine
would not have produced. That suggests the invariant is stronger than its
rationale needs. But it is a deliberate safety property and I am not the author.

**Decision needed:** amend the invariant to entry-origination-only, or decline the
feature. §14.3 recommends not exposing close endpoints until this is settled.

### Q2 — Reset with an open position *(blocking)*

The plan specifies reset as restoring the exact initial state but is silent on an
open position. Recreating the broker silently discards it. Recommendation R-8.1 is
`409 POSITION_OPEN`. Alternative: force-close with a distinct `exit_reason` first,
which preserves the audit trail but makes reset a trading operation.

### Q3 — `GET /api/replay` or fold into `/api/session`?

§22.1 recommends folding in, per the plan's own §4.9 single-snapshot principle,
at the cost of widening Phase 16's shipped `SessionResponse`. Needs a decision
because it changes a frozen contract.

### Q4 — Daily Target on realized or unrealized P&L; and does it close the open position?

Recommended: realized only, consistent with Phase 16's refusal to expose unrealized
P&L, and no forced close. Both are judgement calls with P&L consequences.

### Q5 — Target overshoot semantics

§10.1 concludes the target **cannot** be hit exactly and can be overshot without
bound. Needs confirmation that this is acceptable product behaviour rather than a
defect to be engineered away. Engineering it away would require a new partial-exit
rule — a research change.

### Q6 — High-Risk qualification rules

Deliberately undefined. Candidates exist but each is a research question. Must be
pre-registered before implementation, as Phase 13 was.

### Q7 — Per-mode starting allocations and cost models

Daily/Manual/High-Risk allocations are unspecified. The mock used 100,000 total;
the engine uses 10,000 (`walkforward.STARTING_BALANCE`). If modes may also differ
in `costs`, cross-mode P&L comparison stops being like-for-like (§13.4).

### Q8 — `start_index` beyond `minimum_history`

Safe because the broker starts flat, so skipping iterations cannot skip an exit
decision (§3.8). Needs a test proving no iteration is skipped *incorrectly* when
`start_index > minimum_history`.

### Q9 — Error code convention

`400` (plan) vs `422` (FastAPI validation) for semantically-invalid values. §21.1
recommends `422` throughout and changing the plan's two codes when the endpoints
are written.

### Q10 — The `current` naming collision

§0.2. Not a question so much as a mandated convention, recorded here because the
collision exists in the source being mirrored and will cause an off-by-one if
carried over.

---

## 27. Summary of guarantees

The properties a correct Phase 17 must have, stated compactly:

1. **Replay is historical.** Closed candles only. No future data, ever. (S-7)
2. **Replay is deterministic.** A pure function of `(cursor, broker, dataset)`.
   (D-1…D-5)
3. **Replay is provably the backtest.** Stepping N times equals the backtest
   prefix at N. (§4.4 T4)
4. **No lookahead.** One bar separates signal from fill, enforced by the slice.
   (ALI-1…3)
5. **No new accounting.** Every figure comes from `PaperBroker` or `stats`. No
   equity, no margin, no reservation, no unrealized P&L.
6. **No new strategy.** `analyze` is called unchanged; the gates are untouched.
   (S-8)
7. **Signal ≠ execution.** The policy is explicit and mode-selectable, which is
   what makes Manual possible and Alerts safe. (§16)
8. **Alerts cannot execute.** Structurally, not by convention. (§12.1)
9. **Capital is isolated by construction.** Separate brokers; a close on one mode
   cannot touch another. (§13, §15.1)
10. **The research record is untouched.** Frozen artifacts and datasets stay
    byte-identical. (S-9)

---

*Phase 17A is a design document. It contains no executable code, modifies no
source file, and changes no recorded research result.*