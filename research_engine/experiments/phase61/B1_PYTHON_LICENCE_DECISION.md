# Phase 61 — B1: Python Package Licence Decision Brief

**Status: `OWNER DECISION REQUIRED` — no licence selected.**
This brief prepares the decision. It does not make it.

---

## 1. Verified current state

| Fact | Evidence path |
|---|---|
| Root `package.json` declares `"license": "MIT"` for npm package `"workspace"` | `/package.json` |
| `pnpm-workspace.yaml` scopes that workspace to `artifacts/*`, `lib/*`, `lib/integrations/*`, `scripts` | `/pnpm-workspace.yaml` |
| **`research_engine` is not in that workspace** | same |
| `research_engine/pyproject.toml` (`crypto-paper-lab` 0.1.0) has **no** `license` field and no licence classifier | `research_engine/pyproject.toml` |
| **No `LICENSE` file exists anywhere in the repository** | tracked-file search across `README|LICENCE|LICENSE|NOTICE|COPYING|COPYRIGHT` returns 3 READMEs only |
| No SPDX headers anywhere | grep |

**Package metadata:** `name = "crypto-paper-lab"`, `version = "0.1.0"`,
`description = "Paper-only BTC/USDT strategy research engine"`,
`requires-python = ">=3.11"`.

**Current legal position:** absent an explicit grant, the Python package is
**all-rights-reserved by default**. Nobody may lawfully copy, modify or
redistribute it.

---

## 2. The code/data distinction — the central point

**Code licensing and data licensing are separate grants, made by different
parties, and neither affects the other.**

| | Who grants | What it covers |
|---|---|---|
| **Code licence** | **This project's owner** | `research_engine/src/**`, tests, tooling |
| **Data licence** | **Binance** (third party) | The Binance Vision archives and every derivative work |
| **ECB terms** | **European Central Bank** (third party) | ECB reference rates |

**Consequence:** the owner can grant whatever code licence they wish **without
altering** the CC BY-NC-SA 4.0 terms that apply to the Binance-derived data.
Granting MIT to the code does **not** make the data MIT; it cannot, because the
owner does not hold the data rights.

---

## 3. Third-party dataset obligations that remain outstanding

These are **independent of B1** and are not resolved by choosing a code licence.

| Obligation | Source | Outstanding? |
|---|---|---|
| Attribution to Binance Vision on redistribution | Vision Dataset Terms §4.5 | Partly — in sidecars and READMEs |
| Derivatives remain CC BY-NC-SA 4.0 | §4.5 | Prose only; no machine-readable marker |
| Non-commercial use only | §3.1, §3.4 | Complied with — paper-only, no revenue |
| No sub-licensing / selling / hosting the data | §4.3 | Complied with |

---

## 4. Options, consequences and trade-offs

| Option | Scope granted | Advantage | Consequence / trade-off |
|---|---|---|---|
| **A. No licence (status quo)** | Nobody may copy, modify or redistribute the Python code | Maximum control; no obligations imposed | Blocks all third-party reuse. Usually an unintentional outcome where the rest of the repo is permissive |
| **B. MIT** | Any use including commercial; redistribution permitted with notice; **no** patent grant | Consistent with the existing JS tooling; simplest; widest reuse | Permits relicensing of derivatives; no patent protection for users |
| **C. Apache-2.0** | As MIT, plus an **explicit patent grant** and a NOTICE obligation | Adds patent clarity, common for larger projects | One more artefact to maintain (NOTICE); slightly heavier |
| **D. BSD-3-Clause** | As MIT, plus a no-endorsement clause | Common for research code; simpler than Apache | No patent grant |
| **E. CC BY-NC-SA 4.0 on code** | Non-commercial only; **share-alike propagates to all derivatives** | Aligns code terms with the data terms | **Any derived work becomes non-commercial.** Conflicts with keeping tooling permissive and separate from data terms |

**A note on option E's compounding effect:** share-alike does not stop at the
code. It attaches a non-commercial restriction to anything built from it. If
that is not the intent, E should not be chosen.

**A note on the asymmetry:** the JS side already declares MIT. Choosing A for
the Python package leaves the repository with two different postures; choosing
B/C/D makes it consistent.

---

## 5. Recommendation

**None.** The deciding factor is **intended reuse**, which is an owner
preference not derivable from any repository evidence. Recommending a licence
here would substitute my assumption for the owner's intent.

If the priority is consistency with the existing JS tooling, **B** is the
conventional match. That is an observation about convention, not a
recommendation to grant.

---

## 6. Uncertainty requiring external evidence

| Uncertainty | Why it matters | Evidence required |
|---|---|---|
| Whether the owner intends third-party reuse at all | Determines whether A or B/C/D is appropriate | Owner's statement — no external source can answer this |
| Whether "workspace" MIT was intended repo-wide | No `LICENSE` file exists, so intent cannot be recovered from the repository | Owner's recollection or an explicit decision |
| Patent exposure of the trading logic | Would favour C over B/D | Legal advice — **outside this project's competence**, and not required to choose |

**No legal interpretation is offered.** Whether a given licence is appropriate is
a question for the owner, potentially with legal counsel. This brief reports
scope and consequence only.

---

## 7. Exact owner decision required

> **"I select option [A / B / C / D / E] for `crypto-paper-lab`, effective
> [date], approved by [name]."**
>
> For B, C or D, also: **"The copyright holder named in the licence header is
> [name]."**

**Not to be done by OpenCode:** selecting an option, adding a `LICENSE` file,
editing `pyproject.toml`, or asserting legal certainty.

---

## 8. What this decision does and does not unblock

| Unblocks | Does not unblock |
|---|---|
| Public release of the repository | B2 (ECB terms) |
| Third-party reuse of the code | B3 (Binance registry) |
| Resolution of B10 #10 (`assert_clean_working_tree` is separate) | The B10/B11 gates, which are research decisions |

**B1 is a release-readiness item, not a research blocker.** An evaluation could
proceed with the Python package unlicensed; a public release could not
comfortably.