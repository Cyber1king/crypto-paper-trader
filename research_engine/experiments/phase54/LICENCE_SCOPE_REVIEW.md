# Phase 54 — Licence Scope Review

**Date:** 2026-10-09
**Purpose:** determine precisely which components each licence statement covers.

---

## 0. Evidence classes used throughout

| Tag | Meaning |
|---|---|
| **[V]** | Verified fact — read from a file or publisher source in this phase |
| **[R]** | Existing project record — a prior phase's documented finding |
| **[P]** | Proposed decision — requires approval, not applied |
| **[U]** | Unresolved — evidence insufficient |
| **[H]** | Human approval required |

---

## 1. Repository tooling licence

**[V]** Root `package.json`:

```json
{ "name": "workspace", "version": "0.0.0", "license": "MIT" }
```

**[V]** `pnpm-workspace.yaml` defines the workspace package set:

```yaml
packages:
  - artifacts/*
  - lib/*
  - lib/integrations/*
  - scripts
```

**[V]** `research_engine/` is **not** in that list. The root `"license": "MIT"`
therefore covers the npm workspace packages — `artifacts/`, `lib/`,
`lib/integrations/`, `scripts` — and **not** the Python research engine.

**[V]** A repository-wide tracked-file search for
`README|LICENCE|LICENSE|NOTICE|COPYING|COPYRIGHT|ATTRIBUT` returns exactly three
files, all READMEs:

```
research_engine/README.md
research_engine/data/oos/README.md
research_engine/src/paper_api/README.md
```

**[V]** **There is no `LICENSE` file anywhere in the repository.**

**[R]** Phase 9 recorded: *"MIT for the tooling; the **data** is CC BY-NC-SA 4.0
plus the Binance Vision Dataset Terms."* That sentence is about the split
between code and data. The MIT half traces to the **upstream Binance
`binance-public-data` repository's** README, which MIT-licences *Binance's own
download tooling*. It is not a licence grant from this project, and it never
covered this project's Python code.

---

## 2. Python package licence status

**[V]** `research_engine/pyproject.toml`:

```
L6  name    = "crypto-paper-lab"
L7  version = "0.1.0"
L8  description = "Paper-only BTC/USDT strategy research engine"
```

**[V]** There is **no `license` field and no licence classifier**. Combined with
the absent `LICENSE` file, the accurate statement is:

> **The Python research engine is unlicensed. Absent an explicit grant, the code
> is all-rights-reserved by default.**

This is the single most concrete licensing gap in the repository. It is not a
data-compliance problem — it is a question of whether the owner wants to grant
anything at all, and to whom.

**[P] [H]** Available choices and their consequences. **No licence is selected
here.**

| Option | Effect | Consequence for this project |
|---|---|---|
| **A. MIT** | Permissive, matches the JS tooling | Consistent repo-wide; permits reuse, modification and redistribution including commercial use. Permits relicensing of derivatives |
| **B. Apache-2.0** | Permissive + explicit patent grant | Consistent repo-wide; adds patent terms and NOTICE obligations. Slightly more machinery to comply with |
| **C. BSD-3-Clause** | Permissive, adds no-n endorsement clause | Consistent repo-wide; common for research code |
| **D. Proprietary / no grant** | Keep all-rights-reserved | Nobody may legally reuse the code. Default today, but usually unintentional |
| **E. CC BY-NC-SA 4.0 on code** | Non-commercial, share-alike | Would propagate a NC restriction to any derived work — **would conflict with the Option A/B desire to keep the tooling permissive and separate from the data's terms** |

**[P]** Note the interaction with data: whichever option is chosen applies to
**the code only**. It does not and cannot alter the CC BY-NC-SA 4.0 terms on the
Binance-derived data, which are set by Binance, not by this project.

**[V]** `research_engine/README.md` now states the position explicitly under
"Tooling — no licence granted", so the ambiguity is at least visible to readers.

---

## 3. Third-party dataset terms

### 3.1 Binance Vision — BTC/USDT, ETH/USDT

**[V]** *Binance Vision Dataset Terms*, **Version 1.0**, last updated
**26 August 2026**, re-fetched in this phase and unchanged from the Phase 52 and
Phase 53 fetches. Provider: NEST EXCHANGE LIMITED (ADGM RIE).

| Clause | Effect |
|---|---|
| §3.1 | Datasets under **CC BY-NC-SA 4.0** |
| §3.4 | **Commercial use strictly excluded**; needs a separate written enterprise agreement |
| §4.1 | Permitted: *"algorithmic historical backtesting for purely personal non-production research"* |
| §4.2–4.4 | Prohibited: live/proprietary execution, commercial order generation, paid signal distribution, integration into commercial products or trading-bot platforms |
| §4.5 | Redistributed derivatives must **attribute Binance Vision** and remain **CC BY-NC-SA 4.0** |
| §1.4 | Amendments apply prospectively; rights to already-downloaded datasets preserved |

**[V]** The upstream repository README's bare `## Licence / MIT` applies to
Binance's tooling. §3.3 of the terms states they are *additional* to the CC
licence and never reduce it. **The data is not MIT.**

### 3.2 European Central Bank — EUR/USD, GBP/USD, USD/JPY

**[V]** The registry asserts `CC BY-NC-SA 4.0`. **A repository-wide search found
no ECB licence documentation in any tracked `.md` or `.txt` file — the label
exists only in `research_registry.json` itself, with no cited source.**

This is a materially different situation from Binance, where the terms are
quoted in eight provenance sidecars and four Phase 9/10 reports. See
`ECB_REGISTRY_CORRECTION_PROPOSAL.md`.

### 3.3 frankfurter.app — retrieval endpoint

**[V]** Serves ECB rates. Its own FAQ: *"The rates themselves fall under each
provider's terms."* Endpoint permissiveness transfers nothing to the payload.

**[V]** Forex data present in the repository:

```
data/phase33/ecb_reference_rates_daily_20240101_20261008.csv
data/phase33/MANIFEST_FOREX_ECB_daily_reference_rates.txt
data/phase33/_forex_meta.json
data/phase33/raw_forex_ecb_daily/ecb_{EURUSD,GBPUSD,USDJPY}_*.json
```

**[V]** The CSV schema is `date,pair,rate,rate_type,source` — **daily reference
fixings, not OHLC**. The manifest opens with *"THIS IS NOT AN OHLC DATASET"* and
records that it *"cannot be loaded by the project's canonical OHLC loader"*.

**No synthetic OHLC was constructed from ECB rates, and none is proposed.** The
manifest's schema choice actively prevents rate/candle confusion.

---

## 4. Attribution and modification-disclosure obligations

| Dataset | Attribution | Modification disclosure | Share-alike | Non-commercial |
|---|---|---|---|---|
| Binance Vision | Required (§4.5) — *"appropriate attribution to Binance Vision"* | Not separately required; attribution must identify the work as derived | **Required (§4.5)** | **Required (§3.4)** |
| ECB | Required — *"the ECB must be cited as the source"* | **Explicitly required** — *"If the information is modified by the user … this must be stated explicitly"* | Not required | Not prohibited by the copyright clause |
| frankfurter | n/a (endpoint) | n/a | n/a | n/a |

**[V]** The modification-disclosure duty is a live obligation for this project's
forex data, because **[V]** the acquisition URLs carried **no `providers=ecb`
pin**:

```
https://api.frankfurter.app/2024-01-01..2026-10-08?from=EUR&to=USD
```

**[V]** Frankfurter's documented default is to **blend** rates across providers
unless a provider filter is supplied, and **[V]** the stored raw JSON contains
keys `amount, base, start_date, end_date, rates` with **no provider or
attribution field**.

**[U]** Whether the stored series are unmodified ECB fixings or provider-blended
values **cannot be determined from the repository**. If blended, ECB's explicit
modification-disclosure condition is triggered and the series is not "ECB
reference rates" unmodified. The `source` column currently reads
`European_Central_Bank_via_frankfurter.app`, which is accurate about provenance
but silent about transformation.

---

## 5. Obligations documented vs obligations discharged

| # | Obligation | Documented | Discharged | Evidence |
|---|---|---|---|---|
| 1 | Binance CC BY-NC-SA terms stated | **Yes** | Yes | 8 provenance sidecars (L46); Phase 9/10/15 reports |
| 2 | Binance permitted/prohibited uses stated | **Yes** | Yes | Same |
| 3 | Binance attribution in the **main README** | **Yes** | **Yes (Phase 53)** | `research_engine/README.md` → `## Data and licensing` |
| 4 | Binance attribution in the **data directory README** | **Yes** | **Yes (Phase 53)** | `data/oos/README.md` banner |
| 5 | Share-alike marking on redistributed derivatives | Partly | **No** | Sidecars carry prose; CSVs carry no licence identifier |
| 6 | Root `NOTICE`/`LICENSE` file | No | **No** | Absent |
| 7 | Python package licence | Documented as absent (Phase 53 README) | **No** | No `license` field, no `LICENSE` |
| 8 | Root MIT scope disambiguated | **Yes** | **Yes (Phase 53)** | README states it excludes this package and the data |
| 9 | ECB licence terms documented in-repo | **No** | **No** | Zero in-repo ECB licence evidence |
| 10 | ECB attribution in any artifact | No | **No** | Forex files carry no ECB citation |
| 11 | ECB modification disclosure | No | **No** | Blending status undetermined |
| 12 | No synthetic OHLC from reference rates | **Yes** | **Yes** | Manifest: *"THIS IS NOT AN OHLC DATASET"* |

**Summary: 6 of 12 discharged, 3 partially, 3 not discharged.** The Binance data
side is in good shape. The **ECB side is entirely undocumented in-repo**, and the
**Python package licence is undecided**.

---

## 6. Unresolved questions

**[U] Q1** Is the forex series ECB-unmodified or provider-blended? Requires
re-querying Frankfurter with `providers=ecb` and comparing, or inspecting the
acquisition code path.

**[U] Q2** Do the ECB **Data Portal** terms (`data.ecb.europa.eu`) differ from
the ECB website terms Phase 53 read? Not verified.

**[U] Q3** Is the root `"license": "MIT"` intended to cover the whole repository
by convention, or only the npm workspace it declares? No `LICENSE` file exists
to settle it.

**[U] Q4** Are the 9 normalised `data/oos/*.csv` files and
`data/BTCUSDT_1h.csv` intended as redistributed artifacts requiring §4.5
treatment, or purely local working files? Determines how much share-alike
marking is needed.

---

## 7. Human decisions required

| # | Decision | Evidence to decide on | Blocks |
|---|---|---|---|
| **H1** | Python package licence: A/B/C/D/E (§2) | Owner's intent; no technical constraint | Public release |
| **H2** | Add root `NOTICE.md` (item 6) | §5, §4 of the remediation plan | Nothing — low risk |
| **H3** | Apply share-alike marking to derivatives (item 5) | Q4; note CSV headers would change frozen hashes | Nothing, but **not** via CSV edits |
| **H4** | Approve ECB registry correction | `ECB_REGISTRY_CORRECTION_PROPOSAL.md` | Forex integration |
| **H5** | Whether to re-acquire ECB data with a provider pin | Q1 | Forex integration; moot if forex stays blocked |

**[P] [H]** None of the above was applied in this phase. The single documentation
edit made is recorded in `VERIFICATION.md` §4.