# Phase 61 — B3: Binance Registry State Decision Brief

**Status: `OWNER DECISION REQUIRED` — transition not applied.**
Prior reports describe B3 as "signature-ready". **That status is reconfirmed
below from existing evidence**, per instruction.

---

## 1. Current recorded state

`research_engine/data/research_registry.json`:

| Instrument | `licence_knowledge` | `licence_name` | `licence_note` |
|---|---|---|---|
| BTC/USDT | `UNVERIFIED` | `null` | *"Same unestablished redistribution terms as… "* |
| ETH/USDT | `UNVERIFIED` | `null` | *"Same provider and same unestablished redistribution terms as BTC/USDT."* |

---

## 2. Supporting evidence — exact files and passages

| # | File | Location | What it establishes |
|---|---|---|---|
| 1 | `research_engine/data/oos/raw/BTCUSDT-1h-2026-0{1..8}.provenance.txt` | **L46** | *"Binance Vision data is provided under CC BY-NC-SA 4.0 together with the Binance Vision Dataset Terms. Permitted uses include academic research, non-monetised open educational projects and algorithmic historical backtesting for personal non-production research. Commercial use is excluded. Attribution to Binance Vision is required on redistribution."* — **8 independent per-dataset records** |
| 2 | `research_engine/experiments/phase9/DATA_SOURCE_REVIEW.md` | **L39** | *"Licence \| **Verified.** MIT for the tooling; the **data** is CC BY-NC-SA 4.0 plus the Binance Vision Dataset Terms."* |
| 3 | `research_engine/experiments/phase10/PROVENANCE.md` | **L20** | *"Licence \| CC BY-NC-SA 4.0 + Binance Vision Dataset Terms (non-commercial)"* |
| 4 | `research_engine/experiments/phase10/SUMMARY.md` | **L164** | *"**Licence.** Binance data is CC BY-NC-SA 4.0, non-commercial only."* |
| 5 | `research_engine/experiments/phase10/DATA_QUALITY_REPORT.md` | **L115** | Same |
| 6 | `research_engine/README.md` | `## Data and licensing` | Attribution + CC BY-NC-SA 4.0 + permitted/prohibited uses |
| 7 | `research_engine/data/oos/README.md` | banner | Same, for the data directory |
| 8 | Binance Vision Dataset Terms **v1.0, 26 Aug 2026**, §3.1 | publisher | *"Datasets are provided to You under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International Public License"* |

**Eight in-repository records plus the publisher's own current text.** The terms
were re-fetched and unchanged across Phases 52, 53, 55 and 59.

---

## 3. Schema validity

**[V]** `research_engine/src/crypto_paper_lab/registry_schema.py`:

```python
L89  LICENSE_KNOWLEDGE = frozenset({"VERIFIED", "UNVERIFIED", "RESTRICTED"})
L307 _one_of(entry["licence_knowledge"], LICENSE_KNOWLEDGE, "licence_knowledge", where)
L86-88  #: Licence states this repository can state with confidence.
        #: Anything else must be recorded as UNVERIFIED rather than guessed.
```

`UNVERIFIED → VERIFIED` is a **permitted value**. The transition is schema-valid.

---

## 4. Proposed target state

Applied identically to **BTC/USDT** and **ETH/USDT**:

```
BEFORE  licence_knowledge : "UNVERIFIED"
        licence_name      : null
        licence_note      : "Same provider and same unestablished
                            redistribution terms as BTC/USDT."   [ETH]

AFTER   licence_knowledge : "VERIFIED"
        licence_name      : "CC BY-NC-SA 4.0"
        licence_note      : "Binance Vision Dataset Terms v1.0 (26 Aug 2026) s3.1:
                            datasets under CC BY-NC-SA 4.0. s4.5: attribution to
                            Binance Vision required on redistribution; derivative
                            works remain CC BY-NC-SA 4.0. s3.4: commercial use
                            excluded without a separate written enterprise
                            data licence. s4.1: personal non-production
                            backtesting permitted."
```

**No other field changes.** `attribution_required` is already `true`.
`provenance_grade` is already `A`.

---

## 5. Reconfirmation of "signature-ready"

**Confirmed.** The status means: the evidence is complete and in-repository, the
transition is schema-valid, and the exact before/after values are specified.
**It does not mean approved.** No owner signature exists.

---

## 6. Obligations still outstanding — independent of this transition

| # | Obligation | Source | State |
|---|---|---|---|
| 1 | Attribution in provenance sidecars | §4.5 | ✅ Done — 8 files |
| 2 | Attribution in READMEs | §4.5 | ✅ Done — Phase 53 |
| 3 | Derivative works marked CC BY-NC-SA 4.0 | §4.5 | ⚠️ **Prose only**; no machine-readable marker on the CSVs |
| 4 | Root `NOTICE`/`LICENSE` file | convention | ❌ Absent |
| 5 | Non-commercial use only | §3.4 | ✅ Complied with |
| 6 | No sub-licensing/hosting of the data | §4.3 | ✅ Complied with |

**Items 3 and 4 are outstanding but do not block the registry transition.** Note
that adding a licence header row to a frozen CSV would change its SHA-256 and
invalidate recorded provenance — a sidecar or `NOTICE` file is the correct
vehicle.

---

## 7. Remaining ambiguity

| Ambiguity | Assessment |
|---|---|
| Does `licence_knowledge: VERIFIED` mean "terms verified" or "data verified"? | The schema comment supports the former: it governs *licence statements*, and `provenance_grade` already carries data quality separately |
| Are the ETH bytes actually Binance-sourced? | **[V] Yes** — SHA-256 matches `7507c100…`, and the Phase 33 manifest records the source. Provenance grade A |
| Could the ECB transition's precedent change this? | No — different publisher, different terms |

**No material ambiguity remains.**

---

## 8. What the transition does and does not do

| Does | Does not |
|---|---|
| Make the registry agree with its own repository's evidence | Grant any new right |
| Remove the false implication that redistribution terms are unestablished | Change the Binance Vision terms themselves |
| Reflect the publisher's current published terms | Unblock B10/B11 — those are research gates |

**No legal conclusion is asserted.** The transition records what the publisher
publishes.

---

## 9. Exact owner decision required

> **"I approve the B3 transition to `licence_knowledge: VERIFIED` /
> `licence_name: CC BY-NC-SA 4.0` with the `licence_note` as written, for
> BTC/USDT and ETH/USDT. Approved by [name], [date]."**

**Not to be done by OpenCode:** editing `research_registry.json`, or applying the
transition in any form. **This brief does not apply it.**