# Phase 63 — Owner Decision Packet (B1–B9)

**Prerequisites:** Phase 61 and Phase 62 reports; existing decision registers.
**Safety check at start:** ETH checksum MATCH · reservation `RESERVED/false/null`
· no new blocker.
**No option selected. No decision approved.**

---

## 1. Status summary

| ID | Decision | Status | Owner input needed |
|---|---|---|---|
| B1 | Python package licence | OPEN — owner preference | Option + copyright holder |
| B2 | ECB terms correction | **Evidence captured** · awaiting decision | Approve correction |
| B3 | Binance registry state | **Signature-ready** | Signature |
| B4 | ECB provenance | OPEN — provenance unrecoverable | Defer or reacquire |
| B5 | Minimum trade count | OPEN — owner judgement | Value + method |
| B6 | Four uncertainty parameters | OPEN | 4 values |
| B7 | Result interpretation | OPEN | Bar + confidence level |
| B8 | Cross-asset approver | OPEN — identity required | Name + date |
| B9 | Option A confirmation | OPEN | Confirm or redirect |

---

## 2. B1 — Python package licence

**Status:** OPEN · **Evidence:** `pyproject.toml` has no `license` field; root
`package.json` MIT covers only the npm workspace (`artifacts/`, `lib/`,
`scripts`); no `LICENSE` file exists.
**Options:** A none · B MIT · C Apache-2.0 · D BSD-3 · E CC BY-NC-SA 4.0
**Recommended:** none. If consistency with the JS tooling is the priority, **B**.
**Risk:** E propagates a non-commercial restriction to every derived work.
**Dependent gates:** B11 #7 (B1–B4 resolved or waived). Not a B10 blocker.
**Question:** *"Which licence for `crypto-paper-lab`, and who is the copyright holder?"*

---

## 3. B2 — ECB terms correction

**Status:** evidence captured 2026-10-10 · **Evidence:** artifact SHA-256
`424859b8…`, HTTP 200, 107,678 bytes, verbatim conditions.
**What the evidence shows:** the ECB grants **free use with conditions**, not
CC BY-NC-SA. The registry label asserts two obligations the ECB does not impose
and omits three it does, including *"If the information is modified by the user
… this must be stated explicitly."*
**Options:** (a) approve · (b) also capture Data Portal terms · (c) defer (b)
**Recommended:** (a) + (c).
**Risk:** not correcting leaves an unsupported label on the machine-readable
registry a future integration would read.
**Dependent gates:** B11 #7.
**Question:** *"Do I approve the correction, and do I defer Data Portal capture?"*

---

## 4. B3 — Binance registry state

**Status:** **signature-ready** · **Evidence:** 8 provenance sidecars (L46),
4 phase reports, publisher terms v1.0 (26 Aug 2026); schema permits
`UNVERIFIED → VERIFIED` (`registry_schema.py` L89).
**Options:** (a) approve the transition · (b) decline
**Recommended:** (a) — the registry is currently less accurate than the
repository it governs.
**Risk:** none identified; the underlying use is unaffected by the label.
**Dependent gates:** B11 #7.
**Question:** *"Do I approve the transition to `VERIFIED` / `CC BY-NC-SA 4.0`?"*

---

## 5. B4 — ECB provenance

**Status:** OPEN · **Evidence:** acquisition URL had no `providers=ecb` pin;
Frankfurter's default is to blend; raw payload records no provider.
**Options:** A defer · B reacquire + compare
**Recommended:** **A** — forex is blocked on data quality regardless, and B has a
hard ceiling (a new comparison cannot prove what a past response contained).
**Risk of B:** apparent resolution — a matching comparison could be read as
vindication while proving less.
**Dependent gates:** B11 #7.
**Question:** *"Do I select Option A or B?"*

---

## 6. B5 — Minimum trade count

**Status:** OPEN · **Evidence:** BTC holdout 20 trades / 912 bars, recorded as
mechanically clustered; ETH window 6,744 bars; **no ETH trade count exists**.
**Options:** (1) no minimum · (2) absolute floor · (3) floor + clustering caveat
· (4) interval determines adequacy
**Recommended:** structure **3**, value **not recommended**.
**Risk:** too high → `INCONCLUSIVE` near-certain; too low → noise read as signal.
**Dependent gates:** B10 #1; B11 #2.
**Question:** *"Minimum trade count = [N], derived by [method], framing [1–4]."*

---

## 7. B6 — Four uncertainty parameters

**Status:** OPEN · **Canonical names preserved:** **Block length**, **Iteration
count**, **Basis for block length**, **Confidence level**.
**Method proposed:** block bootstrap over time-ordered trade blocks.
**Recommended:** the method; **no parameter value.**
**Risk:** each changes interval width and therefore the verdict. Basis must not
use the ETH 2026 window.
**Coupling:** Confidence level is **not independent** of B7's bar.
**Dependent gates:** B10 #2; B11 #2.
**Question:** *"Block length [N]; iterations [N]; basis [holding horizon / fixed
/ BTC development autocorrelation]; confidence [N]%."*

---

## 8. B7 — Result interpretation

**Status:** OPEN · **Evidence:** every prior period non-distinguishable from
zero; BTC holdout verdict `INCONCLUSIVE`.
**Options:** three-branch `Promising / Inconclusive / Against the hypothesis` ·
two-branch · continuous reporting
**Recommended:** **three-branch** — a two-branch rule would misreport the BTC
holdout's actual `INCONCLUSIVE` as failure.
**Risk:** zero-spread assumption biases **in favour** of the strategy; a
`Promising` verdict must state that real costs are unmodelled.
**Dependent gates:** B10 #3; B11 #2.
**Question:** *"`Promising` requires [estimate AND interval clear [bar]] with
adequacy met. Confidence [N]%."*

---

## 9. B8 — Cross-asset approver

**Status:** OPEN — **no identity exists.** · **Evidence:** `StrategyConfig.asset`
is only a label (`researchguard.py` L13–15); `CrossAssetAuthorization` requires
approver identity and `from_record()` rejects incomplete records.
**Recommended:** no candidate — nominating one would fabricate an approval.
**Risk:** an approver who has not read the frozen protocol makes the record a
formality.
**Dependent gates:** B10 #4 → #9; B11 #2, #4.
**Question:** *"The authorized cross-asset approver is [name/role], dated [date],
having read the frozen preregistration."*

---

## 10. B9 — Option A confirmation

**Status:** OPEN · **Evidence:** the strategy has **no fitted parameters**;
`walk_forward` exposes `config_hash` (records, does not derive); README excludes
optimisation frameworks. Option A needs **no code change**.
**Options:** (a) Option A single preregistered evaluation · (b) direct Option B
**Recommended:** **(a)** — segmentation yields robustness checks, not train/test
generalisation, and adds multiplicity risk to irreversibly consumed evidence.
**Risk:** mis-describing Option B as "walk-forward generalisation" would assert a
guarantee that cannot be tested.
**Dependent gates:** precedes B5–B7 (fixes the protocol's shape first).
**Question:** *"Do I confirm Option A?"*

---

## 11. Recommended order

```
1. B9 confirm Option A        ─┐ no dependencies
2. B3 approve registry change  │
3. B1 choose licence           │
4. B4 defer or reacquire      ─┘
5. B2 approve correction       (evidence ready)

6. B7 framework + bar  ─┐ coupled
7. B6 four parameters   ├─ fix jointly
8. B5 trade count      ─┘

9.  B10 #5-#7 hashes → #10 clean tree → B8 approver → FREEZE
10. B11 #7,#8,#9 → AUTHORISE
```

**Hard rule:** B5, B6 and B7 close **before** any result exists.