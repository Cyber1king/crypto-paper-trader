# Phase 37 — Instrument Readiness Matrix

**Read-only audit.** No instrument is approved by this document.

Status vocabulary, per instruction:

| Status | Meaning |
|---|---|
| **BLOCKED** | A prerequisite is absent and cannot be supplied by work inside this repository alone |
| **INCOMPLETE** | Data-side prerequisites are met; governance artefacts are missing |
| **READY FOR REVIEW** | Every prerequisite is satisfied and documented; formal governance review may begin |

> **`RESEARCH APPROVED` is not used anywhere in this matrix.** No instrument
> meets its gate, and the status is not available for self-assignment.

---

## 1. Master matrix

| Instrument | Market | Data available | Provenance | Integrity | Untouched eval data | Research question + prereg | **STATUS** |
|---|---|---|---|---|---|---|---|
| **BTC/USDT** | crypto spot | 1h OHLCV, through 2026-10-08 | Grade A | Verified | **NONE** | None | **BLOCKED** |
| **ETH/USDT** | crypto spot | 1h OHLCV, 2024-01-01 → 2026-10-08 | **Grade A** | **Verified, 0 mismatches** | **Exists (ETH 2026), not reserved** | **None** | **INCOMPLETE** |
| **EUR/USD** | forex | **daily rate only** | Grade B | Verified | N/A — no OHLC | None | **BLOCKED** |
| **GBP/USD** | forex | **daily rate only** | Grade B | Verified | N/A — no OHLC | None | **BLOCKED** |
| **USD/JPY** | forex | **daily rate only** | Grade B | Verified | N/A — no OHLC | None | **BLOCKED** |

**Nothing is READY FOR REVIEW. Nothing is RESEARCH APPROVED.**

---

## 2. Blocking reasons, by instrument

### 2.1 BTC/USDT — BLOCKED

**Reason: no untouched evaluation data exists.**

| Window | Consumed by |
|---|---|
| 2024-01-01 → 2025-12-31 | Every research phase from Phase 5 |
| 2026-01-01 → 2026-08-31 | Phases 10, 11 |
| 2026-09-01 → 2026-10-08 | **Phase 30B — permanently spent** |
| 2026-10-09 onward | **Does not exist** |

**Cannot be fixed internally.** Requires Binance to publish. Then B1–B8 of the
checklist apply.

**Retirement confirmation:** holdout digest `c475e541…` re-verified unchanged this
phase. `phase30/SUMMARY.md:343` — *"This holdout is now spent."* No re-use
proposed.

### 2.2 ETH/USDT — INCOMPLETE

**Not blocked. Data-side requirements are fully satisfied; governance artefacts
are missing.**

Satisfied: provenance Grade A (41/41 publisher digests matched this phase),
integrity verified with **0 numeric mismatches** across all 24,288
independently re-derived rows, epoch units correctly recorded (8,784 ms +
15,504 µs), continuity perfect, schema canonical.

Missing:

| # | Missing item | Owner |
|---|---|---|
| 1 | Cross-asset scope decision (Phase 32 records cross-asset behaviour as **NOT ESTABLISHED**) | Research lead |
| 2 | A preregistered research question | Research lead |
| 3 | A preregistration naming the exact digest, config, costs, warm-up, evaluation-start and decision rule | Research lead |
| 4 | Formal reservation of the ETH 2026 window in the registry | Governance |
| 5 | Formal `RESEARCH APPROVED` record | Governance |

**Strategic finding recorded this phase:** the engine imposes **no** barrier —
the strategy is fully scale-invariant and `config.asset` is never validated
against the data. ETH would run mechanically without approval. The governance
stage is therefore the *only* control, which is why it must be real.

### 2.3 EUR/USD, GBP/USD, USD/JPY — BLOCKED

**Reason: no suitable market data exists.**

Verified this phase: the only file is a 5-column
`date,pair,rate,rate_type,source` dataset with **no open, high, low, close or
volume column**, Grade B provenance. It is a daily official reference fixing, not
a traded bar.

Two independent blockers per instrument:

| # | Blocker | Fixable internally? |
|---|---|---|
| 1 | No genuine hourly OHLC market data | **No** — needs an external source |
| 2 | No session / holiday / DST validation library exists | **Yes** — but must be built first regardless |

---

## 3. Governance stage ledger

Per `RESEARCH_GOVERNANCE.md` §2.

| Instrument | Stage reached | Next stage blocked by |
|---|---|---|
| BTC/USDT | EVALUATED (exhausted) | Absence of new data |
| ETH/USDT | PROVENANCE VERIFIED (Grade A) | Missing scope decision, question, preregistration |
| EUR/USD | PROVENANCE VERIFIED (Grade B) | Wrong data type entirely |
| GBP/USD | PROVENANCE VERIFIED (Grade B) | Wrong data type entirely |
| USD/JPY | PROVENANCE VERIFIED (Grade B) | Wrong data type entirely |

---

## 4. Critical-path view

| Instrument | What advances it | Fixable here? |
|---|---|---|
| **ETH/USDT** | Write scope decision, question, preregistration; reserve the window | **Yes — entirely** |
| **BTC/USDT** | Wait for Binance to publish, then acquire and approve | No — external |
| **Forex ×3** | Acquire real OHLC **and** build session/DST validation | Partly — engineering is internal, data is not |

**ETH is the only instrument that can be advanced by work inside this
repository.**

---

## 5. What must NOT be inferred from this matrix

| This matrix says | It does **not** say |
|---|---|
| ETH data is verified | ETH is approved |
| ETH integrity is Grade A | ETH results will be meaningful |
| ETH has untouched 2026 data | ETH 2026 will yield enough trades — **unknown; trade rate never measured** |
| BTC is blocked | BTC strategy failed — it was inconclusive |
| Forex is blocked | Forex is unsuitable for research generally |
| Integrity approval ≠ research approval | Integrity approval is close to research approval |

**The standing conclusion is unchanged: no reliable profitability has been
established for this strategy.** No readiness assessment alters it.

---

## 6. A note on `READY FOR REVIEW`

That status is intentionally **unused**. It would become available only when:

1. every data contract item is satisfied and independently re-verified;
2. provenance is Grade A, or Grade B with the limitation disclosed;
3. a specific, preregistered research question exists;
4. an untouched evaluation window is identified **and reserved**;
5. the instrument's scope is explicitly in bounds.

ETH satisfies 1, 2 and partially 4. It fails 3 and the scope element of 5, so
**INCOMPLETE** is the correct status — not READY FOR REVIEW, and certainly not
approved.