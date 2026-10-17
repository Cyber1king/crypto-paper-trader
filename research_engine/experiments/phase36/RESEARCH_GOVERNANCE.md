# Phase 36 — Research Governance

**Status: SPECIFICATION ONLY. No stage was advanced. No dataset was approved.**

---

## 1. Lifecycle

```
  DISCOVERED
      │  eligible? no ─────────────────────────► REJECTED
      ▼
  DATA CHECKED
      │  integrity contract C1–C14 satisfied?
      ▼
  PROVENANCE VERIFIED
      │  source authenticity evidence adequate?
      ▼
  RESEARCH APPROVED
      │  untouched evaluation data available? no ─► BLOCKED (no evaluation)
      ▼
  EVALUATED
      │  preregistered decision rule applied, whatever it says
      ▼
  MONITORED
      │  data superseded / finding raised / drift
      └──► back to DATA CHECKED, or RETIRED
```

**Every stage is a gate that can be refused.** `RESEARCH_APPROVED` is not a
formality: it is the stage that asserts *suitable, untouched evaluation data
exists*.

---

## 2. Stage definitions

### DISCOVERED

Instrument exists at a venue and has a registry record.

**Entry:** listing observed, record created with every mandatory field populated
or explicitly `unknown`.
**Rejection:** market type unsupported; no meaningful history; licence incompatible;
data requires credentials; semantics not fully specifiable.
**Cannot:** confer eligibility, quality or approval. Discovery never approves.

### DATA CHECKED

The data contract (`MULTI_MARKET_ARCHITECTURE.md` §4) is satisfied.

**Entry:** C1–C14 all pass, verified by recomputation, not by a recorded claim.
**Rejection:** any contract item fails.
**Standing precedent:** the Phase 34 audit set the standard — re-deriving all
24,288 ETH rows from checksummed archives with code independent of the
repository's own acquisition library produced **zero numeric mismatches**. A
recorded PASS statement is not evidence.

### PROVENANCE VERIFIED

Source authenticity evidence is assessed and **graded honestly**.

| Grade | Requirement |
|---|---|
| **A — publisher-authenticated** | Publisher digest exists and was matched before parsing (crypto: 41/41) |
| **B — locally-integrated only** | No publisher digest exists; local SHA-256 recorded, **explicitly not** authenticating the source (forex/ECB) |

**Entry:** grade assigned with evidence; licence and attribution recorded.
**Rejection:** source cannot be identified, or licence forbids this use.
**Precedent:** the ECB dataset is Grade B. Its manifest states local checksums
"establish LOCAL INTEGRITY ONLY … They do NOT establish independent source
authenticity." Grade B must never be presented as Grade A.

### RESEARCH APPROVED

**The most consequential gate. Passing integrity does not pass this stage.**

**Entry requires all of:**
1. Data contract satisfied at Grade A or B, with the grade disclosed.
2. **Suitable, untouched evaluation data exists** for the specific question.
3. Zero overlap with any consumed research or validation window.
4. A preregistration exists, frozen, naming the exact dataset digest.
5. Instrument scope is explicitly in bounds — e.g. Phase 32 records cross-asset
   behaviour as **NOT ESTABLISHED**, so ETH evaluation needs that resolved first.
6. Licence permits the intended use.

**Rejection:** any item missing. In particular, **item 2 is currently unsatisfiable
for BTC.**

### EVALUATED

**Entry:** RESEARCH APPROVED, plus a frozen preregistration naming dataset digest,
configuration, costs, warm-up, evaluation-start, exact metrics and the full
decision rule.
**Constraint:** run **once**. Results reported whatever they say. The spent BTC
holdout is permanently retired and can never return.
**Rejection of the *result* is not permitted.** A null or negative result is a
recorded outcome, not grounds for re-running.

### MONITORED

**Entry:** evaluation recorded; instrument under continued observation.
**Triggers returning to DATA CHECKED:** new data materially changes the picture,
a data-quality finding is raised, the source restates history, licence changes.
**Exit:** RETIRED — record preserved, **never deleted**, because `consumed_windows`
is the anti-reuse evidence.

---

## 3. Current status of every known instrument

| Instrument | Stage | Blocker |
|---|---|---|
| **BTC/USDT** | EVALUATED (exhausted) | **No untouched validation data.** 2026-09…10 holdout is SPENT and permanently retired. Unseen data begins 2026-10-09, once Binance publishes |
| **ETH/USDT** | PROVENANCE VERIFIED (Grade A) | Not RESEARCH APPROVED. Needs: cross-asset scope decision; a preregistration; **untouched evaluation data for the question being asked** |
| **EUR/USD** | PROVENANCE VERIFIED (Grade B) | Granularity insufficient — daily reference rate, not OHLC. Not executable-price data |
| **GBP/USD** | as above | as above |
| **USD/JPY** | as above | as above |

**No instrument is currently RESEARCH APPROVED.**

---

## 4. Anti-reuse rules

| Rule | Statement |
|---|---|
| **A1** | The Phase 30B BTC holdout (2026-09-01 → 2026-10-08, SHA `c475e541…`) is **permanently retired**. It may be read as a historical record. It may never validate, select, tune or compare anything |
| **A2** | Overlapping **dates** on a **different instrument** is not contamination — ETH on 2024–2025 is genuinely new information. It is also **not** an independent sample for BTC research, and must never be described as one |
| **A3** | Any use of a window that influenced a decision **spends** it permanently |
| **A4** | `consumed_windows` in the registry is the authoritative anti-reuse record |
| **A5** | A result that contradicts the standing conclusion does not overturn it; a result that agrees does not confirm it |
| **A6** | Repeated experimentation on one window followed by presenting the best result as independent validation is forbidden (`RESEARCH_STATE.json:394-402`) |
| **A7** | Pooling consumed data to enlarge a sample is manufactured validation (`RESEARCH_STATE.json:400`) |

---

## 5. Standing conclusion

**Unchanged. No reliable profitability has been established for this strategy**
(`RESEARCH_STATE.json:14`). Across 23,376 hourly candles, 12+ configurations and
two full evaluation periods there is no evidence of a profitable trading rule.

Every recorded result is `negative_conclusion` or `diagnostic_only`; **no stage
supports a positive conclusion** (`RESEARCH_CHECKPOINT.md:337-340`).

**Governance exists to test that conclusion properly — not to assume its
reversal, and not to work around it.**

---

## 6. What acquisition does not buy

Explicitly, because it is the most common failure mode:

| Passing | Does **not** imply |
|---|---|
| Integrity checks (C1–C14) | That the dataset may be used for evaluation |
| Checksum verification | Source authenticity when no publisher digest exists |
| Provenance verification | Research approval |
| Research approval | That any result will be positive |
| A positive result | Profitability, reliability or a deployable edge |
| A full year of ETH data | An independent BTC sample |

---

## 7. Acceptance criteria for a future governance implementation

| # | Criterion |
|---|---|
| G1 | No transition to `RESEARCH APPROVED` is possible without a registered untouched window |
| G2 | The spent BTC holdout is rejected by the governance check — proven by test |
| G3 | Grade B datasets cannot be presented as Grade A — proven by test |
| G4 | Every stage transition records timestamp, actor and reason |
| G5 | `RETIRED` is reachable and deletion is impossible |
| G6 | A dataset passing all data checks still cannot advance without approval |
| G7 | Preregistration digest mismatch blocks evaluation — proven by test |
| G8 | Overlap with any `consumed_windows` entry blocks approval — proven by test |

---

## 8. Out of scope

- Advancing any instrument to any stage.
- Approving any dataset for validation.
- Any backtest, evaluation or performance calculation.
- Any strategy, parameter, cost or code change.