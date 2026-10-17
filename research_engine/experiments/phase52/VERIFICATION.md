# Phase 52 Verification

**Date:** 2026-10-09

---

## 1. What was verified, and against what

| Question | Method | Outcome |
|---|---|---|
| How many UNVERIFIED sources? | Parsed `research_registry.json` | **2 entries, 1 publisher** — not four |
| Where did "four" come from? | Read Phase 47 + Phase 50 text | 4 *recorded items*, 3 distinct publishers, 1 in active use |
| Binance Vision licence | Fetched publisher's own `TERMS_AND_CONDITIONS` | **CC BY-NC-SA 4.0**, v1.0, 26 Aug 2026 |
| Is the repo's "MIT" the data licence? | Read full README | **No** — MIT covers repo tooling; data has separate terms |
| Is our use permitted? | Vision terms §4.1 | **Yes** — personal non-production backtesting, named explicitly |
| frankfurter.app rights | Fetched project's own FAQ | Endpoint permissive; **rates follow provider terms** |
| ECB terms | Fetched ECB copyright page | **404 — not re-verified**; registry claim stands unconfirmed |
| Sentiment indices / BLS | Phase 47 records | Unchanged, unadopted, still UNVERIFIED |

Only publisher-controlled text was treated as authoritative. No blog, aggregator
or wrapper documentation was accepted as a licence grant.

---

## 2. Findings that changed the picture

**2.1 — The "four sources" statement was wrong as written.**
`git`-clean parse of the registry returns two UNVERIFIED entries (BTC/USDT,
ETH/USDT) from a single publisher. Phase 50's "Four sources have UNVERIFIED
licensing" conflates one publisher counted twice with two retrieval/candidate
entries that govern nothing in the repository. Recommend correcting Phase 50's
line. Left uncorrected there — editing a frozen report is not this phase's call.

**2.2 — Binance Vision is better than "UNVERIFIED", not worse.**
Personal non-production backtesting is expressly permitted (§4.1). The project's
paper-only posture sits inside the grant. The `UNVERIFIED` marker was
over-cautious, not wrong to hold.

**2.3 — Attribution was already known and never implemented.**
```
attribution_required = True   for all 5 instruments (BTC, ETH, EUR, GBP, JPY)
attribution/licence/NOTICE files in repo = 0
```
The registry recorded the obligation. No artefact discharges it. 44
Binance-derived files are git-tracked, including 9 original `.zip` archives.

That combination — obligation recorded, obligation unmet, material already in
version control — is the substantive output of this phase.

**2.4 — Two exposures did not exist, contrary to expectation.**
The ETH reserved archive is **not** tracked, and no ECB/frankfurter material is
tracked. The Phase 51 governance dataset and the unresolved-provenance data are
both local-only.

---

## 3. Commands run

```
python -X utf8 -c "…"          registry parse: licence_knowledge, reservations
git ls-files                    tracked-file census, licence/notice file search
git status --porcelain          working-tree state
Get-FileHash -Algorithm SHA256  artifact digests
web fetch ×4                    publisher-controlled documents
```

No engine code was executed. No backtest, no trade generation, no performance
computation, no ETH 2026 inspection. Phase 52 read files and web pages; it did
not touch the strategy path.

---

## 4. Integrity — unchanged

**ETH reservation** (`ETH-2026-RESERVATION`), re-read at end of Phase 52:

```
status             : RESERVED
used               : false
preregistration_id : null
dataset SHA-256    : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  MATCH
```

**Artifacts verified this phase:**

| Artifact | Result |
|---|---|
| ETH reserved dataset | full digest **MATCH** |
| Phase 30 `RESULTS_holdout.json` | prefix `4d69a2e2` OK |
| Phase 29 `PREREGISTRATION.md` | prefix `b06f36e2` OK |

Full digests for the remaining nine frozen artifacts were **not** re-derived
here; Phase 51's table already records them at prefix granularity and is scoped
as such. Stating it plainly so the table is not read as stronger than it is.

---

## 5. Files created (3)

- `experiments/phase52/SOURCE_LICENSING_AUDIT.md`
- `experiments/phase52/PERMISSION_MATRIX.md`
- `experiments/phase52/VERIFICATION.md`

**Also corrected:** `experiments/phase51/VERIFICATION.md` §1 and §6 — the
reservation was described from the wrong registry path (`evidence_reservation`
on the instrument; it is actually top-level `reservations[]`), and the frozen
hash table overstated digest granularity.

**Not modified:** no source file, no test, no data file, no registry entry.
`src/`, `data/` and `tests/` show only the pre-existing Phase 39–50 changes.

**Deliberately not done:** the attribution/notice file. Adding a licence file to
a tracked working tree is a change requiring approval, not an audit action.
Recommended wording is drafted in `PERMISSION_MATRIX.md` §6 for that purpose.

---

## 6. Git state

```
branch  main
HEAD    dccebbd53ee8365474345506db9099b13356b53c   (== origin/main, unchanged)
staged  0
new     research_engine/experiments/phase51/  (3 docs)
        research_engine/experiments/phase52/  (3 docs)
```

Nothing staged, committed or pushed.

---

## 7. Status

**Phase 52: AUDIT COMPLETE. No registry transition performed.**

The four unresolved items resolve as: one **resolved with a permissive grant**
(Binance Vision), two **confirmed unresolved and still blocked** (sentiment
indices, BLS), one **confirmed as a wrapper that grants nothing** (frankfurter).

`licence_knowledge` for BTC/USDT and ETH/USDT remains `UNVERIFIED` in the
registry. Phase 52 produced the evidence to change it and deliberately did not
change it — flipping provenance state is a governed transition requiring
approval, and the audit's job is to make the decision available, not to take it.

**Recommended for approval, in order:**

1. Add Binance Vision attribution + CC BY-NC-SA notice — closes a live §4.5
   obligation on 44 tracked files.
2. Update `licence_knowledge` to `VERIFIED` / `CC BY-NC-SA 4.0` on BTC/USDT and
   ETH/USDT, with `licence_note` citing Vision Dataset Terms v1.0.
3. Correct the "four sources" line in the Phase 50 security audit.
4. Re-verify ECB terms from the ECB's own notice, closing the transitive
   provenance path.

**Nothing here grants permission to evaluate ETH.** That remains blocked behind
the eight open Phase 51 decisions, a frozen preregistration, and separate
evaluate authorization.