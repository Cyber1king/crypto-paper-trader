# Phase 54 Verification

**Date:** 2026-10-09
**Remit:** governance, documentation and verification only.

---

## 1. Baseline — Step 1

**[V] Git**

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `dccebbd53ee8365474345506db9099b13356b53c` |
| Upstream | `origin/main` @ `dccebbd53ee8365474345506db9099b13356b53c` |
| Ahead / behind | **0 / 0** |
| Staged | **0** |
| Tracked modified | 19 |
| Untracked | 333 |

**[V] Phase 53 deliverables** — all five present and non-empty:
`LICENCE_REMEDIATION_PLAN.md` (12,852 b), `ECB_RIGHTS_REVIEW.md` (9,083 b),
`ETH_EVALUATION_DESIGN.md` (13,534 b), `PREREGISTRATION_DECISION_REGISTER.md`
(11,388 b), `VERIFICATION.md` (10,727 b).

**[V] ETH dataset SHA-256** — recomputed independently:

```
7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb
```

**MATCH** against the expected value and against the reservation entry.

**[V] Registry / reservation**

```
registry version : 2
reservation_id   : ETH-2026-RESERVATION
status           : RESERVED
used             : False
preregistration_id : None
dataset_sha256   : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb
```

**No discrepancy against prior records. Nothing required investigation.**

---

## 2. Licensing scope — Step 2

**[V]** Root `package.json` declares `"license": "MIT"` for the npm package
`"workspace"`.

**[V]** `pnpm-workspace.yaml` scopes that workspace to `artifacts/*`, `lib/*`,
`lib/integrations/*`, `scripts`. **`research_engine` is not in it.**

**[V]** `research_engine/pyproject.toml` declares **no `license` field and no
licence classifier**.

**[V]** **No `LICENSE` file exists anywhere in the repository.** A tracked-file
search for README/LICENSE/NOTICE/COPYING/COPYRIGHT/ATTRIBUTION returns exactly
three READMEs.

**Conclusion:** the MIT declaration covers the npm workspace only. The Python
research engine is **unlicensed — all-rights-reserved by default**. Phase 9's
phrase *"MIT for the tooling"* traces to the upstream Binance repository's README
and never granted anything from this project.

**[V]** No licence was selected on the owner's behalf. Five options with
consequences are set out in `LICENCE_SCOPE_REVIEW.md` §2 for decision **H1**.

---

## 3. ECB registry correction — Step 3

**[V] Independent verification of in-repo evidence:**

```
$ git grep -In "ECB" -- "*.md" "*.txt" | grep -Ei "licen|copyright|CC BY|terms|attribut|reproduc"
  (no results)
```

**There is no ECB licence documentation anywhere in the tracked repository.**
The `CC BY-NC-SA 4.0` label exists only inside `research_registry.json`, with no
URL, retrieval date, or quoted source.

This is the substantive Step 3 finding. Phase 53 established that ECB's own
current text does not support the label; Phase 54 establishes that **the label
was never sourced in the first place**. Phase 53's statement was not treated as
proof.

**[V]** Phase 54 did **not** re-fetch the ECB page; the instruction asked for
independent verification of *repository* evidence, and that evidence is nil. The
correction proposal requires capturing the page into the repository as a dated
citation so this cannot recur.

**[V]** Additional finding, independently derived: the Phase 33 acquisition URLs
carry **no `providers=ecb` pin**; Frankfurter's documented default is to blend
across providers; and the stored raw JSON (`amount, base, start_date, end_date,
rates`) carries **no provider or attribution field**. Whether the stored values
are unmodified ECB fixings is **unresolved and not determinable from the
repository**.

**Proposed, not applied:** `licence_name` → descriptive ECB policy label;
`licence_note` → the actual conditions with citation and retrieval date;
`licence_knowledge` unchanged at `VERIFIED` (with the alternative position
recorded). **[V]** `licence_name` is free text, so the change is schema-valid.

**No registry state was changed. No legal conclusion is asserted. No ECB rate
was used; no new integration begun; no rate converted into synthetic OHLC.**

---

## 4. ETH evaluation design — Step 4

**[V]** Option A confirmed as recommended, on the verified finding that the
strategy has **no fitted parameters** — `walkforward.py` exposes `config_hash`
but no parameter estimation, and the README states optimisation frameworks are
deliberately excluded. Segmentation therefore yields *segmented out-of-sample
evaluation*, not train/test generalisation, and must not be described as the
latter.

**[V]** Option A requires **no code change**. `run_backtest` already accepts a
`ResearchContext` and invokes `assert_series_permitted` unconditionally
(`backtest.py` L155–181).

**[V]** No safeguard is weakened by Option A. Active controls verified: series
fingerprinting of the candles actually passed to the engine; mandatory
`evaluation_start`; fail-closed registry handling; absence of any `skip_guard`
flag; `CrossAssetAuthorization` enforcement; consumption requiring an explicit
`registry_file`; recording of refusals.

**[V] Safeguards that are application-level, not security boundaries** — stated
plainly in `ETH_EVALUATION_READINESS.md` §6:

- `run_backtest` passes `mark_used=False` **unconditionally**; it never consumes
  a reservation. Single-use protection is discharged by the caller invoking
  `consume_reservation()`, so **a reserved window can be evaluated repeatedly**
  if that call is omitted. This is a protocol obligation, not an enforced
  invariant.
- The registry is plain JSON with no signature or access control.
- `assert_clean_working_tree()` reads git state and is bypassed outside a repo.
- Hashes detect dataset change, not registry tampering.

**[V]** A seven-gate approval sequence (Gates 0–5) is proposed. Gate 4 requires
`consume_reservation()` to run **before** results are interpreted.

**Nothing was implemented. No evaluation was run. The reserved window was not
touched.**

---

## 5. Preregistration register — Step 5

**[V]** The eight canonical decisions P1–P8 are recorded with evidence, proposed
defaults, rationale, consequences, approval requirement, and finalizability, and
are cross-mapped to Phase 51/53's D-1…D-8 so no earlier decision is lost.

**[V]** **All eight remain OPEN.** Four require owner-supplied inputs:
`[OWNER]` minimum trade count (P5), block length and iterations (P6), decision
bar (P7), approver name and date (P8).

**[V]** **No profitability threshold was invented or selected.** Every numeric
gate is marked `[OWNER]`.

**[V]** **The reserved ETH evaluation window was not inspected to inform any
entry.** No ETH 2026 performance figure appears anywhere in the register,
because none has been computed.

**[V]** **No preregistration frozen. No ID assigned or reserved.**

---

## 6. Documentation changes applied — Step 6

One edit, to an ordinary documentation error confirmed against the repository:

| File | Error | Fix | Reason |
|---|---|---|---|
| `research_engine/README.md` | Example calls `load_ohlcv_csv("data/btc_usdt_1h.csv")` — **that file does not exist** | Changed to `"data/BTCUSDT_1h.csv"` | **[V]** `Test-Path data/btc_usdt_1h.csv` → `False`; actual file is `data/BTCUSDT_1h.csv` |

**[V] Checked and deliberately *not* changed:** the README's "Data format" section
shows a `timestamp,open,high,low,close,volume` header while project files use
`Date,Open,...`. `load_ohlcv_csv` accepts **both** (`data.py` L70–73), so the
documented example is valid input, not an error. Changing it would have been an
unnecessary edit.

**[V]** Two README modifications from Phase 53 remain in the working tree and
were preserved: the `## Data and licensing` section and the `data/oos/README.md`
banner.

**Nothing else was edited.** No registry entry, no source file, no test, no
dataset, no frozen artifact, no historical research record. No governed state
changed. No approval self-granted.

---

## 7. Tests — Step 7

**[V] Command**

```bash
cd research_engine
python -X utf8 -m pytest tests -q --no-header -p no:cacheprovider
```

**[V] Result**

```
2499 passed in 1538.08s (0:25:38)
exit code: 0
```

**Failures: 0.** Identical count to the Phase 50 and Phase 53 baselines. No
pre-existing failure was observed, so the question of whether any failure
pre-dated this phase does not arise.

### Did the test run exercise the ETH reservation or evaluation path?

**No — verified, not assumed.**

| Evidence | Finding |
|---|---|
| `test_research_guard.py` module docstring (L4) | States explicitly that no ETH 2026 performance *"is produced or inspected here"* |
| Guard fixtures | Synthetic: `ETH_HASH = "a" * 64` — a fabricated placeholder hash, not the real dataset |
| Guard registries | Built in `tmp_path` via `write_registry(...)`; `consume_reservation(...)` calls pass `registry_file=path` |
| `test_consumption_requires_a_writable_registry_file` | Calls `consume_reservation("ETH-2026-RESERVATION")` with **no** `registry_file` and asserts it **raises** `ResearchGuardError("no registry_file")` — consumption is refused, so the real registry cannot be reached |
| Real ETH CSV references | `test_dataset_validation.py`, `test_data_pipeline.py` — **structural validation only** (schema, row counts, boundaries). No backtest, no trades, no performance |
| `test_research_api.py` | Asserts `research_registry.json` is **not** exposed in the API body |
| Direct `run_backtest` calls in the test suite | **1** |

**[V]** Post-run re-verification confirmed the reservation was untouched:
`status: RESERVED`, `used: False`, `preregistration_id: None`, no
`used_preregistration_id` key present.

---

## 8. Integrity and change control — final state

| Check | Result |
|---|---|
| ETH dataset SHA-256 | **MATCH** (recomputed after the test run) |
| Reservation `status` | `RESERVED` |
| Reservation `used` | `false` |
| Reservation `preregistration_id` | `null` |
| Frozen artifacts modified | **None** |
| Files deleted / reset / cleaned | **None** |
| Staged / committed / pushed / published | **None** |
| Backtests, parameter searches, optimisation | **None** |
| Reserved ETH window consumed | **No** |
| Reference rates converted to synthetic OHLC | **No** |
| Live trading / credentials / real-money execution | **None** — paper-only scope preserved |

**[V]** Final git state: `HEAD` unchanged at `dccebbd5…`, staged `0`.
Phase 54 changes: `M research_engine/README.md` (cumulative, including the Phase
53 section) and new `research_engine/experiments/phase54/`.

---

## 9. Deliverables

| # | File | Contents |
|---|---|---|
| 1 | `LICENCE_SCOPE_REVIEW.md` | Five-way distinction; verified scope; unsourced-licence finding; five options for the Python package with consequences, none selected |
| 2 | `ECB_REGISTRY_CORRECTION_PROPOSAL.md` | Existing → proposed values, evidence and retrieval date, attribution and modification-disclosure duties, blending uncertainty, transition requirements |
| 3 | `ETH_EVALUATION_READINESS.md` | Option A review; segmentation analysis; safeguards; application-level limits; Gates 0–5 |
| 4 | `PREREGISTRATION_DECISION_REGISTER.md` | P1–P8 with cross-mapping to D-1…D-8 |
| 5 | `VERIFICATION.md` | This document |

Each distinguishes verified facts, existing project records, proposed
decisions, unresolved questions, and human approval required.

---

## 10. Readiness verdict

# `READY FOR HUMAN APPROVAL`

**This does not authorise the evaluation.** It means Phase 54's remit —
governance, documentation and verification — is complete, every remaining item
is a **human decision rather than missing analysis**, and nothing further can
progress without a person.

Not `PARTIAL — BLOCKERS REMAIN`: no blocker requires additional research,
investigation or implementation. Each is a choice reserved to the owner.

Not `BLOCKED`: no integrity failure, no stop condition triggered, no
contradiction unresolved in a way that requires more work before decisions can
be taken.

---

## 11. Remaining blockers — decision required

| # | Blocker | Evidence | Precise decision needed |
|---|---|---|---|
| **B1** | Python package is unlicensed | `pyproject.toml` has no `license`; no `LICENSE` file exists | Choose MIT / Apache-2.0 / BSD-3 / no-grant / CC BY-NC-SA — see `LICENCE_SCOPE_REVIEW.md` §2 |
| **B2** | ECB registry label unsupported by its own publisher's text | Zero in-repo ECB licence evidence; label exists only in the registry | Approve the `licence_name` + `licence_note` correction |
| **B3** | Binance `licence_knowledge` is `UNVERIFIED` despite verified terms | Registry vs. 8 sidecars and Phase 9/10 records | Approve transition to `VERIFIED` / `CC BY-NC-SA 4.0` |
| **B4** | Whether forex values are ECB-unmodified or blended | No `providers=ecb` pin; no provider field in payload | Re-acquire with a provider pin, or defer while forex stays blocked |
| **B5** | Minimum trade count unset | Decision P5 | Supply `[OWNER]` value |
| **B6** | Uncertainty parameters unset | Decision P6 | Supply block length and iteration count |
| **B7** | Decision bar unset | Decision P7 | Supply the `[OWNER]` threshold for `SUPPORTED` |
| **B8** | Cross-asset approver unnamed | Decision P8 | Name approver and date |
| **B9** | Evaluation design unconfirmed | Phase 53 §6 recommended Option A | Confirm Option A, or direct Option B |
| **B10** | No preregistration frozen | Reservation `preregistration_id: null` | Close P1–P8, then freeze and assign an ID |
| **B11** | No evaluate authorisation | Gates 2–4 in `ETH_EVALUATION_READINESS.md` | Separate, explicit approval to consume the window |

**B5–B8 and B11 are the gate-blocking set.** B1–B4 are governance corrections
that should be settled first but do not themselves prevent a preregistration
from being drafted.

**Nothing in this document authorises running an evaluation.**