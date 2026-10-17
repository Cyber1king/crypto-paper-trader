# Phase 56 — Reservation Hardening

**Date:** 2026-10-09
**Covers:** Part 2 (N1 concurrency, evaluation-without-consumption) and Part 3
(N4 audit-log correction).

No backtest was run. The reserved window was not consumed.

---

## 1. Summary

| Item | Finding | Action |
|---|---|---|
| **N1** concurrent consumption | Real race confirmed | **Implemented** portable lock; 11 tests |
| **Evaluation without consumption** | By design; 6 entry points traced | **Documented only** — deliberately not changed |
| **N4** audit-log claim | Docstring overstated implementation | **Docstring corrected** |

---

## 2. N1 — concurrent consumption

### 2.1 Was the race real?

**Yes.** Before this phase the consumption sequence was:

```python
on_disk = load_registry(target)   # read
...mutate in memory...            # decide
os.replace(tmp_name, target)      # write
```

`os.replace` makes the **write** atomic, but read-decide-write is not. Two
processes can both read `used=false`, both pass the Phase 55 duplicate check
(which reads `on_disk`), and both write. The last writer wins, and the surviving
`used_on` / `used_preregistration_id` belong to whichever finished last.

The Phase 55 duplicate-consumption guard does **not** help here — it closes
sequential re-spending, not simultaneous attempts, because both processes
evaluate the check against their own pre-write snapshot.

### 2.2 Implementation

**Mechanism:** a sibling lock file created with `os.O_CREAT | os.O_EXCL`, which is
**atomic on POSIX and on Windows**. Exactly one process can create it.

**Scope:** the lock wraps the *entire* read-decide-write sequence, including the
duplicate check, so the decision and the write cannot be interleaved.

```python
with _registry_lock(target):
    on_disk = load_registry(target)      # re-read under the lock
    ...already_spent check...            # decide under the lock
    ...mutate...
    os.replace(tmp_name, target)         # write under the lock
```

**Properties, each verified by test:**

| Requirement | Implementation | Test |
|---|---|---|
| Cross-platform | `O_CREAT\|O_EXCL` — no `fcntl`/`msvcrt` branch needed | runs on this Windows host |
| Fail closed | A held, non-stale lock raises; nothing is written | `test_lock_is_exclusive` |
| Stale locks handled | Age-based: >30 s is abandoned and broken | `test_stale_lock_is_broken_and_removed` |
| Interruption handled | `contextmanager` + `finally` releases on any exception | `test_lock_is_released_after_an_exception` |
| No corruption | Lock covers read→write; refusal raises before any mutation | `test_registry_is_never_left_partially_written` |
| No leaked artefacts | Temp and lock files removed; asserted | `test_no_stray_temporary_files_remain` |
| Does not wrongly block | Distinct reservations both succeed | `test_concurrent_consumption_of_distinct_reservations_both_succeed` |

**Backward compatible:** no public signature changed. `consume_reservation` and
every existing caller are untouched.

### 2.3 Concurrency test

`test_concurrent_consumption_of_the_same_reservation_has_exactly_one_winner`
uses two threads released by a `threading.Barrier` racing to spend the same
reservation:

```
assert sorted(outcomes) == ["consumed", "refused"]
```

**Exactly one winner**, and the surviving `used_preregistration_id` belongs to
that winner rather than being a blend. Because `O_EXCL` is atomic at the OS
level, this exercises real exclusion rather than a Python-level approximation.

### 2.4 Known limitation — stated, not hidden

**Staleness is judged by age alone** (30 s). No liveness check of the recorded
PID is performed, because a portable `is-alive` test differs between POSIX and
Windows and adding one would need a platform branch or a dependency.

Consequence: a holder still alive but descheduled beyond the threshold could
have its lock broken. Accepted trade-off — the guarded operation is a small file
rewrite, not a long job, so a 30 s stall is not expected. A PID-liveness check
would close this and is the obvious next hardening step.

---

## 3. Evaluation without consumption

### 3.1 Entry points traced

| Module | Entry point | Guard | Consumes? |
|---|---|---|---|
| `backtest.py` | `run_backtest` (L65) | `assert_series_permitted` (L157) | **No** — `mark_used=False` (L180) |
| `experiment.py` | `run_experiment` (L16) | none directly | No — forwards context (L39) |
| `yearly.py` | `run_yearly_backtests` (L24) | none directly | No — forwards context (L52) |
| `walkforward.py` | `run_window` (L491), `walk_forward` (L616) | 2 guard calls | No |
| `replay.py` | replay session | `assert_series_permitted(series, research_context=None)` (L583) | No |
| `app.py` | `replay_state` / `_start` / `_pause` / `_step` / `_reset` | via replay | No |

**[V]** Every path that can reach the engine eventually passes through
`run_backtest`, whose guard runs unconditionally. **No entry point bypasses the
guard.** `replay.py` is the notable one: it deliberately passes
`research_context=None`, so replaying a reserved series is **refused** rather
than silently permitted.

### 3.2 How reserved data can be evaluated without consumption

**[V]** Two distinct paths:

1. **With a valid context, repeatedly.** Supply a `ResearchContext` and call
   `run_backtest` any number of times. Each call is permitted; none consumes.
   Only an explicit `consume_reservation()` changes the state.
2. **Consumed series, for development.** `assert_series_permitted` *permits* a
   **consumed** series and records `consumed_series_development_use=True` so an
   audit can distinguish mechanical development from research validation. This is
   deliberate and documented: the engine, dashboard and tests legitimately replay
   BTC data, and blocking it "would break engineering work without adding
   protection to a window that is already spent."

### 3.3 Decision — documented, not changed

**Not implemented.** The task explicitly cautioned: *"Do not blindly make every
backtest consume a reservation; ordinary historical development and permitted
paper research may depend on existing behavior."*

The existing behaviour is **correct and deliberate**. `consume_reservation`'s
docstring states the rationale: a window "should be spent by an evaluation, not
by an attempt", so a guard failure or a crash mid-run cannot silently spend a
window that produced no result. Auto-consuming would invert that and would break
`consumed_series_development_use`, which the dashboard and tests rely on.

**Proposed distinction (design only — needs owner approval):**

| Mode | Trigger | Guard behaviour | Consumption |
|---|---|---|---|
| **Development** | Unregistered series, or an explicitly consumed one | Permitted, marked `consumed_series_development_use` | Never |
| **Reserved evaluation** | Series matches a `RESERVED` entry **and** a valid `ResearchContext` is supplied | Refused unless context matches byte for byte | **Required** — the caller must invoke `consume_reservation()` |

The gap is that step 3's obligation is **procedural**. A minimal implementation
would make `ResearchContext` carry an explicit
`consume_on_completion: bool = False`, letting an evaluation declare its intent
up front and be refused at the guard if it declares consumption but cannot record
it. That is a public-API change with backward-compatible defaulting, but it
changes an established contract, so it is **documented for approval rather than
applied**.

**Interim mitigation (procedural, no code change):** Gate 4 of the evaluation
protocol requires `consume_reservation()` to run **immediately after the run and
before any result is read**. Consuming first makes re-evaluation impossible even
when a result disappoints — which is precisely the moment the temptation arises.

---

## 4. N4 — audit-log correction

**[V] The claim, at line 29:**

> *"**Every attempt is recorded**, including refused ones, so a refusal cannot be
> silently repeated."*

**[V] The behaviour:** `_consume_reservations` writes only on **successful**
consumption. A refusal raises and leaves the registry untouched. **No refusal is
persisted anywhere.**

### 4.1 Correction applied

Replaced with an accurate description:

> **A refusal is not persisted, by design.** This module records *outcomes*, not
> an attempt log: a successful consumption writes `used`, `used_on` and
> `used_preregistration_id`, and a refusal leaves the registry untouched. A
> refused attempt is therefore reported to the caller in the raised error but is
> not durable in the registry. An append-only attempt log was considered and not
> built; adding one would mean new on-disk state and a new failure surface for a
> guarantee the design does not otherwise depend on.

### 4.2 Why documentation, not an audit log

**[V]** The task preferred the minimal correction unless the governance contract
requires refusal logging. **The contract does not require it.** The module's
guarantee is *"evaluated once only"* — a property of **successful** spends. A
refusal log would add new on-disk state, a new failure surface (what if the log
write fails after the registry write succeeds?), and a new privacy question (what
does an attempt log record about who tried what?), without strengthening any
guarantee the design relies on.

The original claim also had a second, weaker half — *"so a refusal cannot be
silently repeated"*. That is **not** achieved by the current design: repeating a
refusal simply raises again. It is not asserted any more.

---

## 5. Test summary

| Suite | Result | Exit |
|---|---|---|
| `tests/test_registry_locking.py` (new, 11 tests) | **11 passed** in 0.30s | **0** |
| Single-use + guard + schema (214) | **214 passed** in 10.74s | **0** |
| Full suite | **2517 passed** in 1872.71s | **0** |

**2517 = 2499 baseline + 7 (Phase 55) + 11 (Phase 56).** No regression.

All tests use temporary registries with synthetic reservations. One test per file
asserts the real registry is byte-identical and the ETH reservation is
`RESERVED` / `used: false` / `preregistration_id: null` / no consumption fields.

---

## 6. What remains open

| # | Item | Status |
|---|---|---|
| **N1-a** | PID-liveness staleness check | Open — needs platform branch or dependency |
| **N1-b** | Cross-process test (current test is threaded) | Open — `multiprocessing` would be stronger but adds flakiness risk |
| **Eval-consumption** | `consume_on_completion` field | **Design documented; needs owner approval** |
| **N4** | Append-only attempt log | Rejected in favour of the docstring correction; reversible by owner decision |