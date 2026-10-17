# Phase 53 — Licence Remediation Plan

**Date:** 2026-10-09
**Scope:** Binance Vision licensing, attribution and share-alike obligations
**Evidence:** Binance Vision Dataset Terms v1.0, 26 August 2026, re-fetched and
re-read in full for this phase.

---

## 1. Correction to Phase 52 — the central finding of this phase

**Phase 52 reported that attribution was missing and that 44 tracked files
carried an undischarged obligation. That was wrong.**

Phase 52 searched for files whose *names* matched `licence|notice|attribut|copyright`
and found none, then reported "no attribution exists". It never searched file
*contents*. Searching content shows the opposite:

```
$ git grep -Iln "Binance Vision" -- "*.md" "*.txt"
  data/oos/README.md
  data/oos/raw/BTCUSDT-1h-2026-0{1..8}.provenance.txt
  data/oos/raw/UNAVAILABLE_MONTHS.txt
  experiments/phase9/{ACQUISITION_PLAN,DATA_SOURCE_REVIEW,SUMMARY}.md
  experiments/phase10/{CHECKSUM_REPORT,DOWNLOAD_REPORT,PROVENANCE,SUMMARY}.md
  experiments/phase10/DATA_QUALITY_REPORT.md
  experiments/phase15/RESEARCH_CHECKPOINT.md

$ git grep -In "CC BY-NC-SA" -- "*.md" "*.txt"
  18 hits, including all 8 provenance sidecars (L46) and Phase 9/10 reports
```

Every raw archive already carries a sidecar with this licence section, already
written before Phase 52 claimed it did not exist:

```
LICENCE
--------------------------------------------------------------
  Binance Vision data is provided under CC BY-NC-SA 4.0 together
  with the Binance Vision Dataset Terms. Permitted uses include
  academic research, non-monetised open educational projects and
  algorithmic historical backtesting for personal non-production
  research. Commercial use is excluded. Attribution to Binance
  Vision is required on redistribution.

This sidecar is a local record created by this project. It is not
issued by Binance.
```

And Phase 9, seventeen phases earlier, had already recorded the licence split
correctly:

> `DATA_SOURCE_REVIEW.md` L39: *"Licence | **Verified.** MIT for the tooling;
> the **data** is CC BY-NC-SA 4.0 plus the Binance Vision Dataset Terms."*

**Consequence:** this repository is not in the state Phase 52 described. The
attribution obligation under §4.5 is *substantially* discharged at the point of
each dataset, via per-archive sidecars. The real gaps are narrower and are
listed in §4. Phase 52's `SECURITY`-style finding should not be relied upon.

The methodological lesson is recorded rather than buried: a filename search
cannot establish the absence of a notice.

---

## 2. Applicable terms

| Item | Value |
|---|---|
| Publisher | NEST EXCHANGE LIMITED, ADGM Recognised Investment Exchange (§1.3) |
| Document | Binance Vision Dataset Terms, **Version 1.0** |
| Last updated | **26 August 2026** |
| Licence | **CC BY-NC-SA 4.0** (§3.1), plus the Vision Dataset Terms |
| Commercial use | **Strictly excluded**; requires a separate written enterprise agreement (§3.4) |
| Retroactivity | Amendments apply prospectively; rights to already-downloaded datasets are preserved (§1.4) |

The upstream `binance-public-data` README ends with a bare `## Licence / MIT`.
That MIT covers the repository's **own tooling**. The README's own *Dataset
Terms* section redirects to `TERMS_AND_CONDITIONS.md`, and §3.3 states the
Vision terms are *additional* to the CC licence and never reduce it. The data is
therefore **not** MIT. Reading the README's last line as covering the archives
would be the single most costly misreading available here.

### Obligations that actually bind

| Clause | Obligation | Status in this repo |
|---|---|---|
| §3.1–3.2 | Datasets under CC BY-NC-SA 4.0 | Recorded in 8 sidecars + Phase 9/10 docs |
| §4.1 | Personal non-production backtesting permitted | **This project's use — inside the grant** |
| §4.5a | Redistributed derivatives attribute Binance Vision | **Partially met** — sidecars only; no README/notice (§4) |
| §4.5b | Redistributed derivatives remain CC BY-NC-SA 4.0 | **Not machine-readable** — no licence header on CSVs (§4) |
| §3.4 | No commercial use without enterprise agreement | Compliant — paper-only, no revenue |
| §4.2–4.4 | No live trading, no paid signals, no commercial product | Compliant |
| §8.2–8.3 | No implied endorsement; name not used to market | Compliant — name used descriptively only |

---

## 3. Affected tracked files

```
data/oos/raw/*.zip                        9 archives   (raw Datasets)
data/oos/raw/*.zip.CHECKSUM               9 files      (raw)
data/oos/raw/*.provenance.txt            9 files      (contains LICENCE section)
data/oos/binance_spot_*_2026??.csv       9 files      (normalised derivative works)
data/oos/binance_spot_*_2026??.csv.report.txt  9 files (derivative)
data/BTCUSDT_1h.csv                              (derivative, main research set)
data/BTCUSDT_1h_Cleaned (1).csv                  (derivative, frozen BTC research set)
data/oos/README.md                                (source named; licence now added)
research_engine/README.md                         (silent; licence now added)
```

**Not affected:** `data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv` (ETH
reserved archive) — **untracked**, with its own `MANIFEST` and manifest-sidecar
licence text. No ECB/frankfurter material is tracked.

---

## 4. The actual gaps, after correction

**Gap 1 — The front door was silent.** `research_engine/README.md` carried no
data-source, licence or attribution statement, and presented data as something
the *user* supplies ("Provide a CSV with these headers") while the repository
itself ships eleven Binance-derived CSVs. A reader had no way to learn the data
was CC BY-NC-SA rather than MIT. *(Remediated in this phase.)*

**Gap 2 — The data directory named the source but not the licence.**
`data/oos/README.md` stated "Source | Binance Vision" while carrying no CC
BY-NC-SA statement and no attribution line. The directory holding the archives
and derivatives was the least well-marked place in the repo.
*(Remediated in this phase.)*

**Gap 3 — No machine-readable share-alike marking on derivatives.** The
normalised CSVs carry a bare `Date,Open,High,Low,Close,Volume` header and no
licence identifier, and no file uses SPDX headers. CC BY-NC-SA share-alike is a
legal obligation on redistributed derivative works; nothing in the artefacts
states it. Sidecars carry the prose, but a CSV detached from its sidecar carries
nothing. *Not remediated — see §6.*

**Gap 4 — No `NOTICE`/`LICENSE` file at repository root.** Convention is the
normal carrier for third-party attribution and its absence weakens the record.
*Not remediated — see §6.*

**Gap 5 — The MIT scope is ambiguous and, for this package, wrong.** Root
`package.json` declares `"name": "workspace", "license": "MIT"`, while
`pnpm-workspace.yaml` lists only `artifacts/*`, `lib/*`, `lib/integrations/*`
and `scripts` — **`research_engine` is not in the npm workspace**. Meanwhile
`research_engine/pyproject.toml` (`crypto-paper-lab`) declares **no** `license`
field and no licence classifier, and no `LICENSE` file exists anywhere.

So the accurate position is: the **JavaScript tooling** carries an MIT
declaration; the **Python research engine carries no licence at all**
(all-rights-reserved by default); and **the data is CC BY-NC-SA 4.0**, which is
neither. Phase 9's phrase "MIT for the tooling" is true of the upstream Binance
download tooling and of the JS workspace, but it does not describe this Python
package. *(Scope now stated explicitly in the README — see §5.)*

**Gap 6 — The registry regressed below the repository's own documentation.**
`licence_knowledge` for BTC/USDT and ETH/USDT is `UNVERIFIED`, with
`licence_name: null` and a note reading *"unestablished redistribution terms"*.
Phase 9 recorded the licence as **Verified** and §3.1 establishes it. The
registry is less accurate than the repo it governs. *Not remediated — governed
transition, see §6.*

---

## 5. Changes applied in this phase

Two documentation files were edited. Nothing else was touched.

| File | Change |
|---|---|
| `research_engine/README.md` | Added `## Data and licensing`: Binance Vision attribution, CC BY-NC-SA 4.0 + Dataset Terms citation, permitted/prohibited uses, statement that normalised CSVs are derivative works, explicit "no licence granted" for the tooling, and the note that root `package.json` MIT does not extend here |
| `research_engine/data/oos/README.md` | Added licence/attribution banner at the top covering `raw/*.zip`, normalised CSVs and sidecars |

**Wording provenance.** No licence text was invented. The statements are
reproduced from the Dataset Terms and are consistent with the wording this
project already authored in its Phase 9/10 documents and provenance sidecars.
The terms document was re-fetched on 2026-10-09 and is v1.0, 26 August 2026 —
unchanged from the Phase 52 fetch.

**No compliance is claimed by this change.** Gaps 3–6 remain open, and the
registry has not been corrected. See §6.

---

## 6. Proposed, not applied

| # | Action | Risk | Needs approval |
|---|---|---|---|
| A | Add root `NOTICE.md` aggregating Binance Vision attribution | Low | Yes |
| B | Add `SPDX-License-Identifier` / licence header row to normalised CSVs | Medium — changes frozen-format data files and would alter hashes | Yes |
| C | Set `licence_knowledge` → `VERIFIED`, `licence_name` → `CC BY-NC-SA 4.0` on BTC/USDT and ETH/USDT, with a `licence_note` citing Vision Dataset Terms v1.0 §3.1 | Medium — governed provenance transition | **Yes** |
| D | Correct the registry's ECB licence label (see `ECB_RIGHTS_REVIEW.md`) | Medium | **Yes** |
| E | Add `license` field to `research_engine/pyproject.toml` (e.g. `MIT`) **or** an explicit all-rights-reserved statement | Low, but a real licence grant is an owner decision | Yes |
| F | Add a CI check asserting every `data/oos/raw/*.zip` has a sibling `.provenance.txt` containing a `LICENCE` section | Low — enforcement of an existing invariant | Yes |

Item B is deliberately **not** recommended without care: appending a licence
header row to the normalised CSVs would change their SHA-256 digests and
invalidate recorded provenance, including frozen BTC artifacts. Marking the
files this way would, perversely, destroy their integrity evidence. If
share-alike marking is wanted, a sidecar or `NOTICE.md` is the correct vehicle.

---

## 7. Compatibility and redistribution concerns

1. **Share-alike propagation.** Normalised CSVs are derivative works and remain
   CC BY-NC-SA 4.0. This is compatible with the current non-commercial research
   posture and constrains any future commercial release.
2. **No compatibility with MIT over the data.** Publishing this repository as
   MIT would misstate the data's terms. The README now states the split
   explicitly so the mistake is not made downstream.
3. **Commercialisation would terminate the right.** §3.4 requires a separate
   written enterprise agreement; the existing local copies do not carry over. The
   trigger is first revenue or first external user. Nothing in the codebase
   anticipates revenue, so this is a boundary to state, not a present defect.
4. **Publisher-side continuity.** §5.3 permits Binance to redact or discontinue
   any dataset or endpoint without notice. The tracked archives are therefore
   also a reproducibility hedge — which is a further reason not to touch their
   bytes for a cosmetic header.
5. **Attribution survives detachment.** Provenance sidecars are tracked next to
   their archives, so the §4.5 attribution travels with the data even if a
   single CSV is copied out. This is why the sidecar pattern is sound and should
   be kept.

---

## 8. Verification steps

Once A, C, D and E are approved:

```bash
# 1. Every raw archive has a licence-bearing sidecar
for z in research_engine/data/oos/raw/*.zip; do
  grep -q "CC BY-NC-SA" "${z%.zip}.provenance.txt" \
    || echo "MISSING LICENCE: $z"
done

# 2. Attribution present at both entry points
grep -qi "CC BY-NC-SA" research_engine/README.md
grep -qi "CC BY-NC-SA" research_engine/data/oos/README.md

# 3. Registry licence fields agree with the evidence
python -c "import json;[print(i['instrument_id'],i['licence_knowledge'],i['licence_name']) \
  for i in json.load(open('research_engine/data/research_registry.json'))['instruments']]"

# 4. No tracked file claims MIT over the data
git grep -n '"license"' -- package.json

# 5. Frozen artifacts unchanged after remediation
sha256sum research_engine/data/BTCUSDT_1h_Cleaned\ \(1\).csv   # expect 201a3b15...
sha256sum research_engine/data/phase33/binance_spot_ETHUSDT_1h_202401-202610.csv
                                                    # expect 7507c100...
```

Step 5 is the important one: remediation must not move the frozen digests.