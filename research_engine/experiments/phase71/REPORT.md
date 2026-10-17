# Phase 71 — Six-Mode Paper-Trading Safety Audit

**Prerequisites:** `modes.py`, `high_risk.py`, `schemas.py`, mode tests.
**Safety check at start:** no new blocker.
**No simulation started. No account state changed.**

---

## 1. Verified: exactly six modes

```
modes registered: 6   (modes.py MODES: Mapping[str, ModeSpec], 6 ModeSpec entries)
  standard          Standard
  ai_intelligence   AI Intelligence
  alerts            Alerts
  daily_target      Daily Target — Paper Trading
  manual            Manual — Paper Trading
  high_risk         High-Risk — Paper Trading
```

**[V]** `modes.py` is 420 lines with a `ModeSpec` class (L288) and a
`MODES` mapping (L344) plus `mode_spec(mode)` accessor (L466).

---

## 2. Verified: no live-execution capability exists

A repository-wide search for execution capability returned **only negative
assertions** — every hit documents the *absence* of leverage:

| File:line | Text |
|---|---|
| `high_risk.py` L59 | *"High-Risk defines **no** leverage, margin, borrowing or liquidation co…"* |
| `high_risk.py` L137 | *"…there is no leve…"* |
| `high_risk.py` L168 | *"leverage impossible. This constant mirrors the engine's limit…"* |
| `modes.py` L259 | *"leverage unreachable rather than merely forbidden."* |
| `app.py` L991 | *"…so leverage is unreachable rather th…"* |
| `schemas.py` L125 | *"Not leverage: there is …"* |
| `schemas.py` L754 | *"…`leverage`. There is no leverage an…"* |
| `schemas.py` L1799 | *"paper capital per position, never leverage."* |

**[V] No matches** for `place_order`, `create_order`, `ccxt`, `withdraw`,
`deposit`, or `api_secret` in any source file.

> **There is no exchange connectivity, no order submission, no deposits, no
> withdrawals, and no leverage — anywhere in the codebase.** Leverage is
> described as *"unreachable rather than merely forbidden"*, which is the
> stronger of the two claims.

---

## 3. Mode-by-mode assessment

| Mode | Risk class | Verified boundary | Concerns |
|---|---|---|---|
| **Standard** | Baseline | Uses frozen `RISK_FRACTION`; no leverage | None identified |
| **AI Intelligence** | **Elevated** | **[V] No provider exists**, so no AI→execution path is possible today | **Label implies AI is active.** It is not. See §4 |
| **Alerts** | Observation-only | Must not mutate account state | Confirm alerts cannot place or size |
| **Daily Target** | Elevated | Paper-only; goals, not guarantees | **Must not be presented as a return promise.** See §4 |
| **Manual** | Low | Operator-initiated paper actions | None identified |
| **High-Risk** | Elevated | **[V] No leverage, margin, borrowing or liquidation** | Name may overstate aggressiveness |

---

## 4. Misleading labels and unsupported claims

| # | Finding | Severity |
|---|---|---|
| **M1** | **"AI Intelligence" mode with zero AI providers integrated.** The name advertises a capability that does not exist. A user selecting it gets no AI. | **High** — misrepresentation risk |
| **M2** | **"Daily Target"** could be read as a promised return. Targets are operator-set goals; the project has **no** demonstrated edge — every prior period was non-distinguishable from zero. | **High** if surfaced without the caveat |
| **M3** | **"High-Risk Paper"** — verified safe (no leverage), but the name implies more than paper sizing can deliver. | Medium |
| **M4** | No per-mode documentation stating that **no strategy has a demonstrated edge** | **High** |

**No code was changed.** Renaming modes is a public-API and product decision
requiring owner input.

---

## 5. Hidden mode-specific risks

| Risk | Detail |
|---|---|
| **AI mode without a provider** | Selecting it may surface an error path or a degraded no-op that is indistinguishable from "working" |
| **Alerts mode mutating state** | Observation-only is a claim that must be enforced, not assumed |
| **Daily Target framing** | A target framing implies an expectation; the research record contradicts any such expectation |
| **High-Risk naming** | Verified safe, but invites misreading of the risk actually taken |

---

## 6. Missing tests identified

| Area | Gap |
|---|---|
| Per-mode invariant assertions | Mode tests exist; a **single test asserting no mode reaches an execution path** would harden the whole surface |
| Alerts cannot mutate account state | Needs an explicit test |
| AI mode behaviour with no provider configured | Needs an explicit test asserting a clean, visible failure |
| No-leverage invariant across all modes | Verified by code inspection; not asserted as an automated invariant |

**No test was added.** These belong to a phase with authority to change test
expectations; adding them here would alter behaviour guarantees without
approval.

---

## 7. What is genuinely sound

| Area | Assessment |
|---|---|
| Paper-only enforcement | ✅ **Structural** — no execution code exists to disable |
| Leverage | ✅ **Unreachable**, not merely forbidden |
| Mode registry | ✅ 6 modes, typed `ModeSpec`, `mode_spec()` accessor |
| Risk controls | ✅ Frozen `RISK_FRACTION` used across modes |
| Schema honesty | ✅ Extensive negative assertions in docstrings |
| High-Risk definition | ✅ Explicitly documented as no-leverage |

**[V]** The strongest finding is that the paper-only property is **structural,
not a configuration flag**. There is no code path to live execution, so it
cannot be accidentally enabled.

---

## 8. Required follow-ups (owner decisions)

| # | Item | Type |
|---|---|---|
| 1 | Rename or re-scope **"AI Intelligence"** until providers exist | Product/API decision |
| 2 | Ensure **"Daily Target"** never surfaces without the "no demonstrated edge" caveat | UI/content decision |
| 3 | Add a per-mode document stating **no strategy has a demonstrated edge** | Documentation |
| 4 | Add tests for alerts-does-not-mutate and AI-mode-without-provider | Test changes |

**None was applied.** Items 1–2 change user-visible behaviour; 3–4 change
test and content expectations. All require owner authorization.

---

## 9. Statement of limits

**No simulation was run. No account state was changed. No mode was exercised.**
Findings are from **code and test inspection only**, and are labelled as such.

**No daily return or profitability is claimed or implied anywhere in this
report.** No leverage, live trading, deposits or exchange execution was added.