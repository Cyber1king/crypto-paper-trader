# Phase 59 — Reserved-Evaluation Consumption Design

**Date:** 2026-10-09
**Status:** **DESIGN ONLY — not implemented.** No public behaviour changed.

---

## 1. Current behaviour

`run_backtest` passes `mark_used=False` **unconditionally** (`backtest.py`
L180). `assert_series_permitted` therefore never spends; consumption is a
separate explicit `consume_reservation()` call.

**The rationale is sound and this design preserves it:** *"a window should be
spent by an evaluation, not by an attempt"* — a guard failure or crash must not
consume a window that produced no result.

---

## 2. Entry points

| Module | Entry point | Guard | Consumes? |
|---|---|---|---|
| `backtest.py` | `run_backtest` (L65) | `assert_series_permitted` (L157) | **No** |
| `experiment.py` | `run_experiment` (L16) | none directly | forwards (L39) |
| `yearly.py` | `run_yearly_backtests` (L24) | none directly | forwards (L52) |
| `walkforward.py` | `run_window` (L491), `walk_forward` (L616) | 2 guard calls | No |
| `replay.py` | replay session | `assert_series_permitted(…, research_context=None)` (L583) | No |
| `app.py` | 5 replay endpoints | via replay | No |

**No entry point bypasses the guard.** Replay passes `context=None` and is
therefore *refused* for reserved series.

---

## 3. The four cases

| Case | Trigger | Guard | Consumption |
|---|---|---|---|
| **A. Development** | Unregistered series, or an explicitly **consumed** one | Permitted; consumed series marked `consumed_series_development_use=True` | **Never** |
| **B. Reserved evaluation** | Series matches a `RESERVED` entry **and** a valid `ResearchContext` is supplied | Refused unless every declared field matches | **Required** — currently manual |
| **C. Successful consumption** | `consume_reservation()` on an unspent reservation | Duplicate refused | Writes `used`, `status`, `used_on`, `used_preregistration_id` |
| **D. Failure / interruption** | Guard refusal, exception mid-run, process death | Refusal raises; registry untouched | **None** — stays `RESERVED` |

Case D is what the design gets right today, and what must not regress.

---

## 4. The gap

**In case B, single-use is a protocol obligation, not an enforced invariant.**
The reserved window can be evaluated N times if the caller never calls
`consume_reservation()`.

The dangerous moment is not the first run — it is **after a disappointing
result**, when re-running a variant is tempting. Nothing in the engine prevents
it.

**Existing mitigation (procedural):** consume immediately after the run and
**before any result is read**.

---

## 5. Recommended design — `consume_on_completion`

```python
ResearchContext(..., consume_on_completion: bool = False)
```

| Value | Behaviour |
|---|---|
| `False` (default) | **Unchanged.** Development and paper research untouched |
| `True` | Declared a reserved evaluation. The guard **requires before any bar is processed**: an explicit writable `registry_file`, a matching `preregistration_id`, and a complete `CrossAssetAuthorization`. On normal completion the engine consumes; on exception it does not (case D) |

**Why this one.** Smallest change that closes the gap only where the owner opts
in; backward compatible by default; preserves case D; no new public function.

### Alternatives considered

| Option | Verdict |
|---|---|
| Consume **before** the run | **Rejected** — contradicts the documented rationale; a crash would permanently destroy evidence |
| Dedicated `run_reserved_evaluation()` | Reasonable; greppable, but a new API surface and callers can still reach `run_backtest` directly |
| Status quo + CI check | Detects *after* the result has been seen |

---

## 6. State machine

```
              ┌──────────────┐
              │   RESERVED   │  used=false, preregistration_id=<id>
              └──────┬───────┘
   guard passes,      │  guard refuses ──► (D) no change, error raised
   completes, result  │
   persisted           │
              ┌─────────▼────────┐
              │      USED        │  used=true, status=USED,
              └──────────────────┘  used_on=<ts>, used_preregistration_id=<id>
```

**Impossible transitions:** `USED → RESERVED`; `USED → USED` (re-spend refused
since Phase 55); `RESERVED → USED` under a *different* preregistration id.

**Idempotency:** deliberately **not** idempotent. An idempotent spend would
make a duplicate attempt undetectable and would permit silently rewriting the
audit record — the exact Phase 55 defect.

**Recovery:** a failed run (case D) leaves the window `RESERVED`; the owner may
re-run. Preserved.

---

## 7. Crash windows and result persistence

With consumption after the run, there is a window between "result computed" and
"consumption recorded". Within it:

- the process may die → result exists, window still `RESERVED`;
- the result may be in memory but not on disk;
- the caller may crash before persisting.

**No design closes this without a transactional result store** — the result and
the reservation live in different places.

**Rule that must enter the preregistration:**

> A result that cannot be shown to be paired with a consumption record **must be
> discarded** and the window re-evaluated. It must never be reconciled
> retroactively.

Stated now so it is not discovered later.

---

## 8. Compatibility

| Concern | Assessment |
|---|---|
| Development backtests (case A) | **Unaffected** — default `False` |
| `consumed_series_development_use` | **Unaffected** — that path never carries a reserved window |
| Dashboard replay | **Unaffected** — replay passes `context=None`; reserved series refused |
| Existing tests | Default covers them; **must be verified, not assumed** |
| `run_window` / `walk_forward` | Flag plumbed through; BTC semantics unchanged if defaulted off |

---

## 9. Synthetic test plan

No reserved data required.

| Test | Assertion |
|---|---|
| `test_default_context_does_not_consume` | Unchanged behaviour |
| `test_consume_on_completion_consumes_after_success` | Spent with the right preregistration |
| `test_consume_on_completion_does_not_consume_on_exception` | Case D preserved |
| `test_consume_on_completion_requires_registry_file` | Fail closed |
| `test_consume_on_completion_requires_preregistration_id` | Fail closed |
| `test_consume_on_completion_requires_cross_asset_record` | Fail closed |
| `test_development_backtest_never_consumes` | Case A unaffected |
| `test_replay_of_reserved_series_still_refused` | Unchanged |
| `test_second_evaluation_after_consumption_refused` | Single-use enforced |

---

## 10. Why this is not implemented here

It changes a **public API** (`ResearchContext`) and alters `run_backtest`'s
contract for callers that opt in. That is a governance decision, not an
engineering one.

**The reservation is provably intact and single-use is currently enforced by
protocol.** Closing the gap is worth doing — but it should be done on the
owner's authority, with the test plan above executed first.