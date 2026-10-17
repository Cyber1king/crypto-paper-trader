# Phase 55 — Reservation Enforcement Review

**Date:** 2026-10-09
**Question:** can the reserved ETH window be consumed more than once, or
evaluated without being consumed?

**Short answer: yes to both — but only one is a defect, and it has been fixed.**

No backtest was run. No reserved-period performance was inspected. The
reservation was not consumed.

---

## 1. What the guard already enforces correctly

Before listing gaps, it is worth stating what is sound, because the gaps are
narrower than "no single-use enforcement".

| Control | Location | Verified |
|---|---|---|
| A **consumed** window is refused outright | `assert_evaluation_permitted` | **[V]** |
| A **reserved** window is refused unless a valid `ResearchContext` is supplied | `assert_evaluation_permitted` | **[V]** |
| Series is **fingerprinted**, so omitting the context is not a bypass | `assert_series_permitted` | **[V]** |
| Identity is the dataset **SHA-256**, not a path — a copy cannot evade it | `researchguard.py` L21–22 | **[V]** |
| `run_backtest` raises if a research context is supplied without `evaluation_start` | `backtest.py` L183–187 | **[V]** |
| Cross-asset evaluation requires a complete `CrossAssetAuthorization` | `researchguard.py` L147–162 | **[V]** |
| `consume_reservation` refuses without a writable `registry_file` | `_consume_reservations` L793–799 | **[V]** |
| Consumption requires the reservation to exist | `consume_reservation` L340–344 | **[V]** |
| Registry re-read from disk before edit; replaced via `os.replace` | L802, L839–846 | **[V]** |
| Status moves with the flag (`RESERVED` + `used=true` is schema-invalid) | L813–816 | **[V]** |
| Caller's in-memory registry is mirrored, preventing in-process re-run | L851–857 | **[V]** |
| No `skip_guard` flag anywhere | module docstring L27–28 | **[V]** |
| Empty registry refused — nothing declared is not "nothing protected" | `registry_schema.py` L479 | **[V]** |

The design is careful and mostly right. Two specific gaps remain.

---

## 2. Finding F1 — duplicate consumption accepted, audit trail overwritten

**[V] Confirmed by reading `_consume_reservations` (L773–857).** The mutation loop
unconditionally sets:

```python
entry["used"] = True
entry["status"] = "USED"
entry["used_on"] = now                       # <- new timestamp
entry["used_preregistration_id"] = reported or None   # <- caller's value
```

**It never checks `entry["used"]`.**

**[V] Confirmed empirically** with a synthetic reservation in a temporary
registry:

```
--- first consume (prereg-A) ---
   used = True | status = USED | used_on = 2026-10-10T06:56:40 | used_pre = prereg-A
--- SECOND consume of the SAME reservation (prereg-B) ---
   RESULT: ACCEPTED - no duplicate rejection
   used_pre : prereg-A -> prereg-B
```

**Impact.** The second call is not a no-op. It overwrites
`used_preregistration_id` — *the only durable record of which preregistration
actually spent the window* — and `used_on` — the only record of when. A stray
retry, a re-run script, or a notebook cell would silently rewrite the audit
trail of the single most important governance event in the project's history.

Note the scope precisely: because `assert_evaluation_permitted` **refuses** a
consumed window, this defect does **not** enable a second *evaluation*. It
enables a second *consumption record*, corrupting the evidence that an
evaluation happened exactly once, legitimately.

---

## 3. Finding F2 — evaluation without consumption (by design)

**[V]** `run_backtest` passes `mark_used=False` **unconditionally**
(`backtest.py` L180). `assert_series_permitted` therefore never spends.

The docstring (`backtest.py` L146–150, `consume_reservation` L322–332) explains
the intent: consumption is the caller's explicit post-run decision, so a guard
failure or a crash cannot spend a window that produced no result.

**That rationale is sound** — *"a window should be spent by an evaluation, not by
an attempt."* This is a deliberate design property, not a bug, and it was
deliberately not "fixed".

**[V] But the consequence must be recorded honestly:** with the caller omitting
`consume_reservation()`, a reserved window can be evaluated **repeatedly**.
Nothing detects the omission. Single-use is a **protocol obligation discharged by
discipline**, not an enforced invariant.

Mitigating factor: any *later* evaluation still requires a fresh
`ResearchContext` with a `preregistration_id`, and a consumed window is refused.
So the omission degrades auditability, not immediately the guarantee.

---

## 4. Finding F3 — no inter-process locking (TOCTOU)

**[V]** The consumption path is `load_registry` → mutate → `mkstemp` → `os.replace`.

`os.replace` is atomic **for the write**, but the sequence is a classic
read-modify-write with no lock. Two concurrent processes can both read
`used=False`, both pass every check, and both write. The last writer wins, and
the surviving audit fields are whichever process finished last.

**[V]** Partially mitigated: `_consume_reservations` re-reads `on_disk` at L802
specifically so a stale in-memory registry cannot clobber the file. That closes
the *stale object* hole but not the *concurrent process* hole.

**Not implemented** — see §7.

---

## 5. Required state transitions

**[V]** Observed and enforced by the schema:

```
            freeze preregistration
RESERVED ─────────────────────────────────────► RESERVED + preregistration_id
   │  used=false                                    │  used=false
   │
   │ consume_reservation()  [now duplicate-safe]
   ▼
USED      status=USED, used=true, used_on=<ts>, used_preregistration_id=<id>
```

Invariants the schema enforces: `status` and `used` must agree; `RESERVED` with
`used=true` is refused. A registry missing this pairing is unreadable.

---

## 6. Fix applied in this phase

### 6.1 Duplicate-consumption rejection

**File:** `research_engine/src/crypto_paper_lab/researchguard.py`
**Function:** `_consume_reservations`
**Change:** one guard clause inserted between `by_id` and the mutation loop:

```python
already_spent = sorted(
    str(entry.get("reservation_id"))
    for entry in on_disk["reservations"]
    if isinstance(entry, dict)
    and str(entry.get("reservation_id")) in wanted
    and entry.get("used")
)
if already_spent:
    raise ResearchGuardError(
        "refusing to record consumption: reservation(s) "
        f"{already_spent} are already spent (used=true). ..."
        "Nothing was written."
    )
```

**Why here, and not in `consume_reservation`:** `_consume_reservations` is the
single choke point every consumption path passes through, and it operates on
`on_disk` — the freshly re-read file. Placing the check there closes the race
window that exists between the caller's read and the write, and it protects any
future caller, not just the current one.

**Properties:**

| Property | How |
|---|---|
| Fails closed | Raises `ResearchGuardError`; never falls through |
| Nothing written | Check precedes every mutation and every write |
| Audit preserved | `used_on` / `used_preregistration_id` untouched on refusal |
| All-or-nothing | If any requested reservation is spent, none are mutated |
| Backward compatible | Refusal applies only to an already-spent reservation |

### 6.2 Tests

**New file:** `research_engine/tests/test_reservation_single_use.py` — **7 tests**,
all using **synthetic fixtures**: a temporary registry holding a
`PROBE-SYNTHETIC` reservation. **The reserved ETH dataset is never opened or
evaluated**, and one test explicitly asserts the real registry is byte-identical
afterwards and the ETH reservation is still `RESERVED` / `used: false` /
`preregistration_id: null`.

| Test | Asserts |
|---|---|
| `test_first_consumption_spends_the_reservation` | Normal spend still works |
| `test_second_consumption_is_rejected` | **The F1 defect is closed** |
| `test_rejected_second_consumption_preserves_the_audit_trail` | Registry byte-identical; `used_pre` still `pre-A` |
| `test_rejection_happens_before_any_mutation_of_a_multi_reservation_call` | All-or-nothing |
| `test_consumption_without_a_registry_file_fails_closed` | Existing refusal retained |
| `test_unknown_reservation_is_still_rejected` | Unknown-id refusal retained |
| `test_real_eth_reservation_is_never_touched_by_this_module` | ETH reservation intact |

**[V] Backward-compatibility evidence:** the full suite passes at **2506** (2499
pre-existing + 7 new), exit code 0. No existing test depended on re-consuming a
reservation.

**[V] A test of mine failed initially and the fix was to the test, not the
product.** `test_consumption_still_requires_an_explicit_registry_file` used a
synthetic ID with no `registry_file`; `consume_reservation` resolves the
reservation *before* checking for a writable target, so it raised
`"not in the registry"` instead. Corrected to use the real reservation id — which
does resolve — to exercise the genuine `no registry_file` fail-closed path.

---

## 7. Documented, not implemented

| # | Proposal | Why not applied |
|---|---|---|
| **N1** | **Inter-process lock** around read-modify-write (e.g. an exclusive lockfile or `fcntl`/`msvcrt` locking) | Not portable in a two-line change; requires platform-specific code and a new on-disk artefact. Needs design and its own tests. **The realistic threat model is an accidental double-run, not a concurrent adversary** — and F1, now fixed, catches the accidental case |
| **N2** | **Atomic consume-and-evaluate** (spend at run start rather than after) | Would contradict a deliberate, well-reasoned design property: a crash must not spend a window that produced no result. Reverting a documented design decision is an owner call |
| **N3** | **Mandatory consumption** — have `run_backtest` refuse to run a reserved window unless consumption is guaranteed | Same objection as N2, plus it would break the legitimate pattern of a dry run |
| **N4** | **Append-only audit log** of every consumption attempt (including refusals) | The docstring claims *"every attempt is recorded, including refusals"*. **That claim is not supported by what `_consume_reservations` does** — it records only successful spends into the reservation. Either the docstring is aspirational or an audit log was intended and not built. Worth resolving: the claim currently overstates the implementation |
| **N5** | Registry integrity protection (signature / digest held outside the repo) | The registry is unsigned JSON with no access control. Out of scope for a single phase; noted in Phase 54 §6 as a standing limitation |

**N4 deserves attention.** It is a documentation-versus-implementation mismatch
inside the module's own contract, not a hypothetical. Resolving it is an owner
decision: correct the docstring, or build the log.

---

## 8. Answers to the two questions posed

**Can the reservation be consumed more than once?**
**Before this phase: yes** — accepted, with `used_preregistration_id` and
`used_on` silently overwritten, proven empirically.
**After this phase: no** — refused, with the audit record preserved byte for
byte.

**Can it be evaluated without being consumed?**
**Yes, by design, and deliberately unchanged.** `run_backtest` never consumes.
A forgotten `consume_reservation()` means repeated evaluation is possible and
undetected. The rationale is sound and documented; the residual risk is
procedural, and it is mitigated by making consumption a mandatory, audited step
in the Gate 4 protocol.

---

## 9. Residual safeguards that are application-level, not security boundaries

Unchanged from Phase 54 §6 and restated because they bear directly on this
review:

- `run_backtest` never consumes — single-use is a protocol obligation.
- The registry is unsigned JSON with no access control; a process with write
  access can edit `status` or `used` directly.
- Hashes detect dataset change, not registry tampering.
- `assert_clean_working_tree()` reads git state and is bypassed outside a repo.
- F1 is now fixed; **N1 (concurrency) is not**, so two simultaneous consumers
  could still both write.

**None of this is a security control.** These are guards against accident under
an honest engineer, not resistance to a determined actor.