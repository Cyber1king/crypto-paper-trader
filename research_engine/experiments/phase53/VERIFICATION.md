# Phase 53 Verification

**Date:** 2026-10-09

---

## 1. Headline: Phase 52's central finding was wrong

Phase 52 reported **0** attribution/licence files and an undischarged §4.5
obligation across 44 tracked files. That was produced by searching **file names**
for `licence|notice|attribut|copyright`, not file **contents**.

Searching contents inverts the finding:

| Check | Result |
|---|---|
| Tracked files mentioning "Binance Vision" | **18** |
| Tracked files stating "CC BY-NC-SA" | **18 hits** |
| Raw archives with a licence-bearing `.provenance.txt` sidecar | **8 of 8** (L46) |
| Phase 9 record of the licence split | `DATA_SOURCE_REVIEW.md` L39 — *"Verified"* |

The repo has carried correct CC BY-NC-SA documentation **since Phase 9**,
seventeen phases before Phase 52 claimed it was absent.

**The corrected finding is narrower and is what Phase 53 acted on:** the front
door and the data directory README lacked a licence statement. Those two are now
fixed. The general lesson is recorded in `LICENCE_REMEDIATION_PLAN.md` §1: *a
filename search cannot establish the absence of a notice.*

---

## 2. Audit results

| # | Question | Finding |
|---|---|---|
| 2.1 | Binance-derived tracked files | 44 (9 `.zip`, 9 `.CHECKSUM`, 9 `.provenance.txt`, 9 normalised `.csv`, 9 `.report.txt`, plus `data/BTCUSDT_1h.csv` and the frozen `data/BTCUSDT_1h_Cleaned (1).csv`) |
| 2.2 | Which carry attribution obligations | All — raw Datasets and normalised derivative works alike (§4.5) |
| 2.3 | Which notices are missing | `research_engine/README.md` (**fixed**), `data/oos/README.md` (**fixed**); root `NOTICE.md` and CSV-level share-alike marking (**open, proposed**) |
| 2.4 | Tooling MIT scope | **Root `package.json` MIT covers only the npm workspace** (`artifacts/`, `lib/`, `scripts`); `research_engine` is not in `pnpm-workspace.yaml`. `research_engine/pyproject.toml` declares **no licence**. **No `LICENSE` file exists anywhere.** |
| 2.5 | ECB provenance | ECB does **not** publish under CC BY-NC-SA 4.0 — see §4 |
| 2.6 | ETH reservation metadata | Unchanged — see §5 |

---

## 3. Changes applied

Two files edited. Both documentation. **Every modified file is listed here.**

| File | Change |
|---|---|
| `research_engine/README.md` | Added `## Data and licensing` — Binance Vision attribution, CC BY-NC-SA 4.0 + Dataset Terms v1.0 citation, permitted and prohibited uses, derivative-work status, explicit *"no licence granted"* for the tooling, and the note that root `package.json` MIT does not extend to this package or to the data |
| `research_engine/data/oos/README.md` | Added licence/attribution banner covering `raw/*.zip`, normalised CSVs and sidecars |
| `experiments/phase53/*.md` | 5 new deliverables |

No source file, test, dataset, configuration or registry entry was modified. No
file was deleted, staged, committed, pushed, reset or cleaned.

**No licence text was invented.** Wording is reproduced from the Dataset Terms
and matches statements this project already authored in Phase 9/10 and its
provenance sidecars. The terms were re-fetched 2026-10-09 and are **v1.0, 26
August 2026** — unchanged from the Phase 52 fetch.

**No compliance is claimed.** Gaps 3–6 remain open.

---

## 4. ECB finding — the registry is wrong

`research_registry.json` records EUR/USD, GBP/USD and USD/JPY as
`licence_name: "CC BY-NC-SA 4.0"`.

The ECB's own *Disclaimer & copyright* page states **free use subject to
conditions**: cite the ECB as source; **state modifications explicitly**; give
buyers of sold documents a "free of charge" notice; no framing. Authored Working
and Occasional Papers need prior written authorisation.

It is **not** CC BY-NC-SA 4.0, and the difference is bidirectional:

- The label asserts a **share-alike obligation that does not exist**.
- It asserts a **non-commercial restriction that does not exist** in the
  copyright clause.
- It **omits** the modification-disclosure and resale-notice duties that *are*
  in force.

So the label causes over-compliance in one respect and under-compliance in
another. The registry is the machine-readable surface a future integration
would consult, so this matters beyond documentation.

`licence_knowledge` is left at `VERIFIED` — the right to use these rates for
non-commercial research is established. The **string** is what needs correcting.
Proposed in `LICENCE_REMEDIATION_PLAN.md` §6 item D; not applied, because a
registry write is a governed transition requiring approval.

Frankfurter's own FAQ confirms the layering: *"The rates themselves fall under
each provider's terms."* Endpoint permissiveness transfers nothing.

**No ECB rate was used, and no synthetic OHLC was created.** Forex remains
blocked on data quality.

---

## 5. Integrity — unchanged

**ETH dataset hash — exact, three-way agreement:**

```
actual          7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb
reservation     7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb   MATCH
manifest L19    7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb   MATCH
```

**Reservation `ETH-2026-RESERVATION`:**

```
status               : RESERVED
used                 : False
preregistration_id   : None
warmup_bars          : 17544
evaluation_bars      : 6744
evaluation_start_index : 17544
```

**Frozen artifacts.** The ETH dataset is verified against a complete recorded
digest. For the remaining frozen artifacts, the previously recorded values exist
in prior reports **at prefix granularity only**; those prefixes were re-confirmed
unchanged. This limitation was already flagged in `phase51/VERIFICATION.md` §6
and is restated rather than papered over. No baseline was re-derived.

**Prohibited-workflow compliance:**

| Rule | Verification |
|---|---|
| No backtest / trades / performance | None run. Suite execution only; tests are deterministic fixtures |
| No ETH 2026 performance inspected | Row counts and endpoint timestamps only, re-read from the reservation |
| No BTC holdout reuse | Not loaded; `consumed_windows` untouched |
| No strategy tuning | No config parameter altered |
| Reservation preserved | Verified before and after |
| Frozen artifacts preserved | Verified; no data file written |
| Nothing staged/committed/pushed/reset/cleaned/deleted | Confirmed |
| Test suite | **2499 passed** in 26:47 — identical to the Phase 50 baseline |

---

## 6. ETH evaluation design — summary

**Why BTC-pinned:** `validate_dataset_integrity` compares `DATASET_FIRST` /
`DATASET_LAST` as **bare module constants** (`walkforward.py` L320–328). Count and
hash are *already* overridable parameters (L286–287). The timestamp bounds are
the sole blocker.

**Can it be made asset-agnostic without altering frozen BTC semantics?** **Yes.**
Adding `expected_first` / `expected_last` parameters that default to the current
BTC constants makes every existing call site take the identical branch — BTC
behaviour unchanged, no test perturbed, no frozen artifact touched. The parameters
must default to the BTC constants and **not** to "unchecked", or they would
introduce precisely the caller-supplied bypass `researchguard.py` L27–28 says is
deliberately absent. **Not implemented here.**

**Recommendation: Option A** (single pre-registered ETH window), because the
strategy has **no fitted parameters** — walk-forward here would be segmented
evaluation, not train/test generalisation, so it does not buy what its name
implies, while adding real multiplicity risk to evidence that is consumed
irreversibly. Option B is recommended as a separate later phase on separate data.

**Not implemented. Not authorised.**

---

## 7. Preregistration decisions

All eight remain **OPEN**. None closed by this phase. No preregistration ID
assigned or reserved.

Three (D-1 minimum trades, D-3 decision rule, D-7 design) only have meaning if
closed **before** evaluation. Four require numeric or named-owner inputs marked
`[OWNER]`:

- D-1 minimum trade count — `[OWNER]`
- D-2 block-bootstrap block length — `[OWNER]`
- D-3 decision-rule bar — `[OWNER]`
- D-4 / D-8 named approver and date — `[OWNER]`

**No profitability threshold was invented, and none is proposed.** D-3 adopts a
three-branch rule (`SUPPORTED` / `NOT SUPPORTED` / `INCONCLUSIVE`) because a
two-branch rule would force the BTC holdout's actual `INCONCLUSIVE` outcome into
a failure verdict and destroy the distinction the protocol exists to maintain.

---

## 8. Git state

```
branch  main
HEAD    dccebbd53ee8365474345506db9099b13356b53c   (== origin/main, unchanged)
staged  0
Phase 53 modifications:
  M research_engine/README.md
  M research_engine/data/oos/README.md
  ?? research_engine/experiments/phase53/
```

All other modified/untracked paths are pre-existing Phases 39–52 work.

---

## 9. Open items requiring approval

| # | Item | Risk |
|---|---|---|
| 1 | Correct registry ECB `licence_name` to the actual ECB free-use policy | Medium |
| 2 | Set BTC/ETH `licence_knowledge` → `VERIFIED`, `CC BY-NC-SA 4.0` | Medium |
| 3 | Add root `NOTICE.md` | Low |
| 4 | Add `license` field to `research_engine/pyproject.toml`, or an explicit all-rights-reserved statement | Low (real licence grant = owner decision) |
| 5 | CI check: every `data/oos/raw/*.zip` has a licence-bearing sidecar | Low |
| 6 | Close D-1…D-8, then freeze, then authorise evaluation | Blocking |

**Deliberately not applied:** CSV-level SPDX/share-alike headers. Appending a
licence row to the normalised CSVs would change their SHA-256 digests and
invalidate recorded provenance, including frozen BTC artifacts — marking the
files for licence compliance would destroy their integrity evidence. A sidecar
or `NOTICE.md` is the correct vehicle.

---

## 10. Verdict

**`PHASE 53 COMPLIANCE READINESS: PARTIAL`**

Not `PASS`: the registry's ECB licence label is demonstrably incorrect and
uncorrected; four documented gaps remain open; all eight preregistration
decisions are open; ETH evaluation is not authorised.

Not `FAIL`: the project's actual use — personal, non-production, paper-only
backtesting — sits **inside** the Binance Vision grant (§4.1 names it
expressly); attribution is substantially discharged via eight provenance
sidecars and seventeen prior reports; there is no commercial use, no prohibited
distribution, no implied endorsement; the reservation and frozen artifacts are
byte-identical; and 2499 tests pass.

The compliance posture is materially better than Phase 52 reported, and the
substantive legal position is sound. What is missing is governance accuracy —
a wrong licence string in the machine-readable registry, and decisions that
require an owner rather than a researcher.