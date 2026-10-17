# Phase 58 — Reserved-Evaluation Consumption Design

**Date:** 2026-10-09
**Scope:** Step 4 — how a reserved evaluation should be bound to consumption.

> **Design only. Nothing implemented. No reserved data was evaluated.** This
> document requires explicit governance approval before any code changes.

---

## 1. Current behaviour, verified

`run_backtest` passes `mark_used=False` **unconditionally** (`backtest.py`
L180). `assert_series_permitted` therefore never spends. Consumption is a
separate explicit call to `consume_reservation()`.

The rationale is documented (`backtest.py` L146–150, `consume_reservation`
L322–332): *"a window should be spent by an evaluation, not by an attempt"* — so
a guard failure or a crash mid-run cannot silently spend a window that produced
no result.

**That rationale is sound and this design does not overturn it.**

---

## 2. The six evaluation entry points

| Module | Entry point | Guard | Consumes? |
|---|---|---|---|
| `backtest.py` | `run_backtest` (L65) | `assert_series_permitted` (L157) | **No** — `mark_used=False` |
| `experiment.py` | `run_experiment` (L16) | none directly | forwards context (L39) |
| `yearly.py` | `run_yearly_backtests` (L24) | none directly | forwards context (L52) |
| `walkforward.py` | `run_window` (L491), `walk_forward` (L616) | 2 guard calls | No |
| `replay.py` | replay session | `assert_series_permitted(series, research_context=None)` (L583) | No |
| `app.py` | 5 replay endpoints | via replay | No |

**No entry point bypasses the guard.** Replay is notable: it deliberately passes
`research_context=None`, so replaying a reserved series is **refused** rather
than silently permitted.

---

## 3. The four cases that must be distinguished

| Case | Trigger | Guard | Consumption |
|---|---|---|---|
| **A. Development backtest** | Unregistered series, or an explicitly **consumed** one | Permitted; consumed series marked `consumed_series_development_use=True` | **Never** |
| **B. Reserved evaluation** | Series matches a `RESERVED` entry **and** a valid `ResearchContext` is supplied | Refused unless every declared field matches the reservation | **Required**, and currently a **manual** step |
| **C. Successful consumption** | `consume_reservation()` on an unspent reservation | Duplicate consumption refused (Phase 55) | Writes `used`, `status`, `used_on`, `used_preregistration_id` |
| **D. Failed / interrupted evaluation** | Guard refusal, exception mid-run, or process death | Refusal raises; registry untouched | **None.** Window stays `RESERVED` |

Case D is the one the current design gets right: a failed attempt does **not**
spend the window.

---

## 4. The gap, stated precisely

**In case B, consumption is a protocol obligation, not an enforced invariant.**
`run_backtest` will happily evaluate the reserved window N times if the caller
never calls `consume_reservation()`.

Why this is the residual risk that matters: the dangerous moment is not the
first run — it is the moment **after a disappointing result**, when re-running a
variant is tempting. Nothing in the engine prevents it.

**Mitigation already in place (procedural):** Gate 4 requires
`consume_reservation()` immediately after the run and **before any result is
read**. Consuming first makes re-evaluation impossible even when the result
disappoints.

**Why that is not enough:** it depends on the operator following a sequence, at
the precise moment they are most inclined to deviate.

---

## 5. Design options

### Option 1 — `consume_on_completion` flag on `ResearchContext` *(recommended)*

```python
ResearchContext(
    ...,
    consume_on_completion: bool = False,   # new, default preserves behaviour
)
```

Semantics:
- `False` (default) — **unchanged behaviour**. Development and paper research
  are untouched.
- `True` — the run is declared a *reserved evaluation*. The guard requires an
  explicit writable `registry_file`, a matching `preregistration_id`, and a
  complete `CrossAssetAuthorization`, **before** any bar is processed. On normal
  completion the engine consumes; on exception it does not (case D).

**Advantages:** backward compatible by default; closes the gap only where the
owner opts in; no change to case A; case D preserved.

**Disadvantages:** still cannot distinguish "completed" from "completed but the
result was not persisted" — see §7.

### Option 2 — consume *before* the run

**Rejected.** Contradicts the documented rationale: a crash would spend a window
that produced no result, permanently destroying the evidence. This was
deliberate design, not an oversight.

### Option 3 — a dedicated `run_reserved_evaluation()` entry point

A thin wrapper that refuses to run without a complete authorization, and
consumes in a `finally`-equivalent after the result is persisted.

**Advantages:** the reserved path is a distinct, greppable function; impossible
to reach the reserved window through a general-purpose entry point.

**Disadvantages:** a new public API surface; every future caller must know which
to use; a caller can still reach `run_backtest` directly.

### Option 4 — status quo plus tooling

Keep the API, and add a CI check that flags any run touching a `RESERVED` series
without a following `consume_reservation`.

**Advantages:** zero API change. **Disadvantages:** detects after the fact, and
after the result has been seen.

---

## 6. State machine

```
                    ┌──────────────┐
                    │   RESERVED   │  used=false, preregistration_id=<id>
                    └──────┬───────┘
       guard passes,          │  guard refuses  ──► (D) no change, error raised
       run completes,         │
       result persisted       │
                    ┌─────────▼────────┐
                    │      USED        │  used=true, status=USED,
                    └──────────────────┘  used_on=<ts>, used_preregistration_id=<id>

  Transitions that must be impossible:
    USED  ──► RESERVED   (rollback / reuse)
    USED  ──► USED      (re-spend; refused since Phase 55)
    RESERVED ──► USED with a *different* preregistration_id
```

**Idempotency:** `consume_reservation` is **not** idempotent by design — a
second call is *refused*. That is deliberate: an idempotent spend would make it
impossible to detect a duplicate attempt, and would permit silently rewriting
the audit record (the Phase 55 defect).

**Recovery:** if a run fails (case D), the window stays `RESERVED` and the owner
may re-run. This is the behaviour to preserve.

---

## 7. The persistence window — the honest limitation

Under Option 1, the engine consumes **after** the run returns. Between "result
computed" and "consumption recorded" there is a window in which:

- the process could die → result exists, window still `RESERVED`;
- the result is in memory but not written to disk;
- the caller crashes before persisting.

**No design fully closes this without a transactional result store**, because
the result and the reservation live in different places (memory/disk vs the
registry file).

The practical consequences:
- A crash in that window leaves an **unspent** window whose result was computed
  but not recorded. The correct recovery is to **discard the result** and re-run,
  not to try to reconcile it.
- This is a *protocol* obligation: **a result that cannot be shown to be paired
  with a consumption record must be treated as non-existent.**

**That rule belongs in the preregistration.** It is stated here so it is not
discovered later.

---

## 8. Compatibility with existing behaviour

| Concern | Assessment |
|---|---|
| Development backtests (case A) | **Unaffected** — default `False` |
| `consumed_series_development_use` | **Unaffected** — that path never carries a reserved window |
| Dashboard replay | **Unaffected** — replay passes `context=None` and is refused for reserved series |
| Existing tests | Would need `consume_on_completion=False` explicitly only where a context is passed; default covers it |
| `run_window` / `walk_forward` | Would need the flag plumbed through; BTC semantics unchanged if defaulted off |

**No existing test should break**, because the default preserves behaviour. That
must be *verified*, not assumed, before any merge.

---

## 9. Synthetic test plan (no reserved data required)

| Test | Assertion |
|---|---|
| `test_default_context_does_not_consume` | Unchanged behaviour |
| `test_consume_on_completion_true_consumes_after_success` | Window spent with correct preregistration |
| `test_consume_on_completion_true_does_not_consume_on_exception` | Case D preserved |
| `test_consume_on_completion_requires_registry_file` | Fail closed |
| `test_consume_on_completion_requires_preregistration_id` | Fail closed |
| `test_consume_on_completion_requires_cross_asset_record` | Fail closed |
| `test_development_backtest_never_consumes` | Case A unaffected |
| `test_replay_of_reserved_series_still_refused` | Unchanged |
| `test_second_evaluation_after_consumption_refused` | Single-use enforced |

All with `tmp_path` registries and synthetic reservations, matching existing
practice. **None requires the reserved ETH dataset.**

---

## 10. Recommendation

**Adopt Option 1 (`consume_on_completion`, defaulting off)**, and record the
persistence-window rule from §7 in the preregistration.

This is the smallest change that closes the gap where it matters, leaves every
existing workflow untouched, and preserves the deliberate "a failed attempt does
not spend the window" property.

**Not implemented. Requires explicit approval** — it changes a public API and
alters the contract of `run_backtest` for callers that opt in.