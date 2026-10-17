# Phase 52 — Permission Matrix

**Date:** 2026-10-09
**Companion to:** `SOURCE_LICENSING_AUDIT.md`

---

## 1. Binance Vision — BTC/USDT and ETH/USDT

Governing document: *BINANCE VISION DATASET TERMS* v1.0, 26 August 2026.
Licence: **CC BY-NC-SA 4.0** (§3.1). Provider: NEST EXCHANGE LIMITED (ADGM).

| Activity | Status | Authority |
|---|---|---|
| Download / cache / query | **Permitted** | §2.3, §3.2 |
| Personal, non-production historical backtesting | **Permitted** | §4.1 |
| Academic research | **Permitted** | §4.1 |
| Non-commercial open-source data-science evaluation | **Permitted** | §4.1 |
| Deriving charts, models, indicators | **Permitted, but governed** | §2.4 |
| Live/proprietary trading execution | **Prohibited** | §4.2 |
| Automated **commercial** order generation | **Prohibited** | §4.2 |
| Selling signals to third parties for compensation | **Prohibited** | §4.2 |
| Selling / renting / leasing / hosting the datasets or derivative feeds | **Prohibited** | §4.3 |
| Sub-licensing | **Prohibited** | §4.3 |
| Integration into a commercial financial product or paid newsletter | **Prohibited** | §4.3, §4.4 |
| Integration into a **commercial trading-bot platform** | **Prohibited** | §4.4 |
| Any commercial use at all | **Prohibited** without a separate written enterprise agreement | §3.4 |
| Redistribution of derivatives | **Permitted only with** Binance Vision attribution **and** CC BY-NC-SA 4.0 on the derivative | §4.5 |
| Using "Binance"/"Binance Vision" in marketing a commercial product | **Prohibited** | §8.3 |
| Implying Binance endorsement | **Prohibited** without written consent | §8.2 |
| Scrape to evade rate limits | **Prohibited** | §7.2 |
| Assuming data is error-free or fit for purpose | **No warranty** | §10.2–10.3 |
| Seeding expected outcomes | **Unlawful** | §11.3 |

### Current project posture

| Question | Status |
|---|---|
| Is our use permitted? | **Yes** — personal, non-production, paper-only backtesting; §4.1 names this case |
| Is profit from it permitted? | Not attempted and not contemplated; §3.4 forbids commercial use |
| Do we hold the data correctly? | **No** — attribution owed, no notice file exists |
| Is the data error-free? | Not warranted by anyone (§10.2); our own integrity checks are ours, not Binance's |

**Hard boundary:** if this project ever becomes commercial — a paid product, a
managed strategy, a signal service, a hosted bot — the Binance Vision data
becomes unlicensed for that use, and no retro-fitting of the existing local
copies cures it (§3.4 requires a *separate written enterprise agreement*, not
merely non-removal of the archives). Trigger: first dollar of revenue, or first
external user. Until then, §4.1 governs.

---

## 2. European Central Bank — EUR/USD, GBP/USD, USD/JPY

Registry status: `VERIFIED`, `CC BY-NC-SA 4.0`.
**Not re-verified in this audit** — the ECB copyright page returned HTTP 404 at
the URL consulted. The claim stands unchallenged and unconfirmed.

| Activity | Status | Authority |
|---|---|---|
| Use for research | Permitted, subject to ECB terms | registry claim |
| Redistribution | Subject to ECB terms + attribution | registry claim |
| **Confidence in this row** | **Low — transitive provenance** | see audit §7 |

**Do not treat this row as settled.** Its licence string reached the registry
through a frankfurter dependency rather than from the ECB directly, and Phase 52
exists because transitive provenance is precisely what fails silently. Forex
remains blocked on data-quality grounds independently of licensing, so nothing
operational turns on this today — but the follow-up is owed.

---

## 3. frankfurter.app — retrieval endpoint

Status: **endpoint permissive; payload rights unchanged.**

| Activity | Status |
|---|---|
| Use the API | Free, no key, no quotas (rate-limited against abuse) |
| Commercial use *of the API* | **Yes** — documented as permitted |
| Commercial use *of the ECB rates it returns* | **Governed by ECB**, not by frankfurter |
| Self-hosting | Permitted; project is open source |

Frankfurter's own words: *"The rates themselves fall under each provider's
terms."* The endpoint grants nothing in the values. Never record frankfurter as
the licence source for ECB data.

---

## 4. Crypto sentiment indices — not adopted

| Activity | Status |
|---|---|
| Any use | **Blocked — UNVERIFIED / RESTRICTED** |
| Reason | Proprietary methodology not open to inspection |

Nothing acquired, nothing integrated. Stays blocked until a specific provider is
proposed and its terms actually read.

---

## 5. BLS — not adopted

| Activity | Status |
|---|---|
| Any use | **Blocked — UNVERIFIED** |
| Open question | Rate limits unstated in pages consulted |

---

## 6. Obligations owed by this repository

Derived from §4.5 and CC BY-NC-SA 4.0, applied to what is actually tracked.

| # | Obligation | Current state | Priority |
|---|---|---|---|
| 1 | Attribution notice for Binance Vision | **MISSING** | **High** |
| 2 | CC BY-NC-SA 4.0 marking on redistributed derivatives | **MISSING** | **High** |
| 3 | Keep the ETH reserved archive untracked | **Compliant** | Keep |
| 4 | Do not commercialise without §3.4 enterprise agreement | **Compliant** | Keep |
| 5 | Keep ECB/frankfurter material untracked pending re-verification | **Compliant** | Keep |
| 6 | Re-verify ECB terms from the ECB's own notice | **Owed** | Medium |

Items 1 and 2 are unmet obligations on 44 already-tracked files. They are
remediation work for a subsequent approved phase — **this audit did not create
the notice**, because adding a licence file to the repository is a change to a
tracked working tree and belongs under change control, not under an audit.

Recommended attribution wording, for approval:

> Market data in `data/oos/` and `data/BTCUSDT_1h.csv` originates from
> **Binance Vision** (data.binance.vision), provided under **CC BY-NC-SA 4.0**
> and the Binance Vision Dataset Terms v1.0 (26 August 2026). Binance Vision
> data is used here for personal, non-production research only. See
> `experiments/phase52/SOURCE_LICENSING_AUDIT.md`.