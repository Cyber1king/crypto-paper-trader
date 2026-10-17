# Phase 42 Independent Readiness Audit

**Date:** 2026-10-09
**Nature:** Read-only audit of Phases 39–41. No strategy logic was executed.

This audit assesses the safeguards themselves, not the strategy. Where a claim
could be checked by reading code, it was checked by reading code — several
findings below contradict what the documentation implied.

---

## 1. Guard audit (Step 42.1)

### 1.1 Entry-point coverage — verified by live probe

Each strategy-executing entry point was called with the real reserved ETH series
and no research context. Every one refused.

| Entry point | Direct guard call | Result with reserved ETH, no context |
|---|---|---|
| `run_backtest` | yes | **REFUSED** |
| `replay.Replay.__init__` | yes | **REFUSED** |
| `run_experiment` | no — forwards | **REFUSED** |
| `run_yearly_backtests` | no — forwards | **REFUSED** |
| `run_window` | no — forwards | **REFUSED** |
| `walk_forward` | no — forwards | refused, but see §1.2 |

`test_no_bypass_parameter_on_any_entry_point` confirms no
`skip_guard` / `ignore_guard` / `unsafe` / `allow_reserved` / `bypass_guard` /
`force` / `disable_guard` / `no_research` / `dev_mode` parameter exists on any of
them.

### 1.2 A finding the documentation did not mention

`walk_forward` refused the reserved ETH data — but **not because of the research
guard**. Its own `validate_dataset_integrity` ran first and raised
`WalkForwardValidationError: dataset ends 2026-10-08 23:00:00, expected …`,
because that check is hard-wired to the BTC primary dataset's declared bounds.

So `walk_forward` was protected by an incidental pre-existing check rather than by
the guard under audit. Two consequences worth recording:

- The guard **is** reachable in `walk_forward` (verified: it forwards
  `research_context` to `run_window`, which forwards to `run_backtest`, which
  calls the guard directly). It simply was not what stopped this particular call.
- A different dataset would not trip that bound check, and the guard would then
  be the only protection. That it is present is what matters; that it was
  redundant here is not a defence of it.

This is a case where a passing probe could be read as stronger evidence than it
is. The guard's own refusal was confirmed independently at `run_backtest` and
`run_window`, so the finding does not undermine the coverage claim — but the
reason `walk_forward` refused was not the reason I initially read it as.

### 1.3 Guard ordering verified structurally

In `run_backtest` the guard is called at relative line 77; `PaperBroker` is
constructed at line 124. Refusal happens before any account, position or trade
state exists. Same ordering in `Replay.__init__`.

### 1.4 Missing context fails closed

Verified in code, not inferred from the Phase 39 report. `assert_series_permitted`
fingerprints the candles actually passed in and runs **before** anything is
conditioned on context presence, so omission is not an exemption.

Probed directly against the real ETH file:

| Series | Bars | Result |
|---|---|---|
| Full dataset | 24,288 | REFUSED |
| Evaluation slice | 6,744 | REFUSED |
| Mid-chunk spanning warm-up → evaluation | 4,000 | REFUSED |
| 5-bar slice | 5 | REFUSED |
| Evaluation tail | 100 | REFUSED |
| Warm-up head | 100 | REFUSED |
| Evaluation slice reversed | 6,744 | REFUSED |
| Evaluation, every-other-bar | 3,372 | REFUSED |

### 1.5 Registry persistence

| Property | Verified how |
|---|---|
| File authoritative when named | stale in-memory copy cannot authorise a spent window (`test_registry_file_is_authoritative_when_named`) |
| `mark_used` cannot silently do nothing | refuses with no file to record into |
| Atomic writes | `mkstemp` + `os.replace`; no temp files remain (`test_consumption_write_is_atomic`) |
| Failed persistence blocks proceeding | reservation absent ⇒ nothing written |
| Consumption is explicit and separate | `consume_reservation()` after a successful run; a failed run does not spend a window |
| Changes auditable | `used`, `used_on`, `used_preregistration_id` recorded |

One design decision worth flagging for a future reviewer: Phase 40 moved
consumption out of the guard call and defaulted `mark_used` to `False`. This is
correct — an attempt that crashes must not spend a window — but it does mean a
caller who forgets `consume_reservation()` can run the same window twice. The
window is protected against *unauthorised* reuse, not against *repeat reuse by
someone who followed the process*. That is a deliberate trade-off, not an
oversight.

### 1.6 Overlap status unambiguous

`AcquisitionReport.overlap_check` defaults to `failed`, so a report that never
states an outcome is non-compliant. A bypassed check records `skipped` and a
note reading `NOT verified`.
`test_skipped_is_distinct_from_checked` pins the exact Phase 33 defect: two
reports, both with empty `overlapping_rows`, only one a genuine pass.

### 1.7 Instrument identity enforced

`DatasetIdentity.assert_compatible_with_config` refuses a config `asset` label
that disagrees with the dataset.
`test_btc_label_cannot_silently_load_eth_dataset` confirms a BTC label cannot
load ETH data. The error message points at `CrossAssetAuthorization`, and the
frozen BTC configuration was never modified.

### 1.8 API path cannot bypass

`load_research_candles` calls the guard and records the decision in
`CONSUMED_DATASET_DECISION`. The served dataset is a consumed window, so it is
permitted as recorded development use — blocking it would break the dashboard
without protecting anything already spent. The decision is JSON-serialisable, so
an audit can confirm what was served.

**Correction to the Phase 39 report.** It described this path as refusing the run.
The code at that time called `assert_no_registered_range(allow_consumed=True)`,
which *returns* a list of hits that nothing read — nothing was refused. Phase 40
replaced it with a check that actually records something. The Phase 39 report was
wrong on this point; the underlying conclusion (the path is guarded) held, but
the described mechanism did not do what the text claimed.

---

## 2. Reserved ETH protection (Step 42.2)

Metadata and file integrity only. No signals, no trades, no performance.

```
status             : RESERVED
used               : False
preregistration_id : None
used_on present    : False

expected hash      : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb
actual   hash      : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb
MATCH              : True
```

Declared boundaries:

- Warm-up: `2024-01-01T00:00:00` … `2025-12-31T23:00:00`
- Evaluation: `2026-01-01T00:00:00` … `2026-10-08T23:00:00`, 6,744 bars

All three required values match. The dataset is unmodified and unspent.

---

## 3. Frozen research integrity (Step 42.3)

Digests re-read from the repository's own files and compared against values
recorded earlier. No baseline was re-derived, and nothing was silently updated.

| Artifact | Recorded | Actual | Result |
|---|---|---|---|
| BTC primary dataset | `201a3b15…` | `201a3b15…` | OK |
| Consumed BTC holdout | `c475e541…` | `c475e541…` | OK |
| Phase 29 preregistration | `b06f36e2…` | `b06f36e2…` | OK |
| ETH dataset | `7507c100…` | `7507c100…` | OK |
| Phase 30 `RESULTS_holdout.json` | `4d69a2e2…` | `4d69a2e2…` | OK |
| Phase 30 `RESULTS_holdout.txt` | `fd3f7741…` | `fd3f7741…` | OK |
| Phase 30 `RESULTS_trades.csv` | `174d5587…` | `174d5587…` | OK |
| Phase 30 `SUMMARY.md` | `9e3171b0…` | `9e3171b0…` | OK |

Phase 33–35 provenance artifacts present and unmodified:

| Artifact | SHA-256 |
|---|---|
| `phase33/ACQUISITION_REPORT.md` | `bb4460993f11276f…` |
| `phase34/INDEPENDENT_AUDIT.md` | `e611ecdba5fecc5d…` |
| `phase35/PROVENANCE_CORRECTION.md` | `ee704878251afbe9…` |

**8 of 8 verified, 0 mismatches.**

---

## 4. Conclusions the audit does *not* support

Stating these because an audit that only lists confirmations is not an audit.

1. **No safeguard was bypassed during these three phases.** Verified by
   construction: every entry point refuses the reserved series before any trading
   state exists.
2. **This says nothing about profitability.** 2157 passing tests establish that
   guards refuse unauthorised work and validators refuse malformed data. Not one
   of them bears on whether the strategy has an edge. No profitability threshold
   is asserted anywhere in Phases 39–42.
3. **Passing safeguards are not readiness.** ETH's data is the cleanest in the
   repository and its validation is the strongest — and it is still unapproved,
   because the blockers are governance and preregistration, not data quality.
4. **The guards are not tamper-proof.** They are Python functions in a
   repository anyone can edit. They raise the cost of a mistake; they do not
   prevent a determined actor, and they are not a security boundary.
5. **`walk_forward`'s ETH refusal was incidental**, as detailed in §1.2. The
   guard would have caught it, but something else did first.

---

## 5. Overall assessment

The safeguards implemented across Phases 39–41 are present, load-bearing, and
independently verified by probing the real entry points rather than by reading
their documentation. Where documentation was found to overstate what code did —
twice, in Phase 39's API-guard description and in the incidental
`walk_forward` refusal — that is recorded above rather than smoothed over.

The ETH window is protected and unspent. No evaluation is approved. Forex
remains blocked on data and calendar grounds that no amount of validation code
can address.

Remaining gaps, carried forward:

| Gap | Why it remains |
|---|---|
| Unregistered series are permitted | Data the registry has never seen cannot be identified; closing it means requiring context for every series |
| Sub-threshold slices (1–2 bars) unmatched | Inert: the engine needs >22 bars before any signal can exist |
| Repeat reuse possible if `consume_reservation()` is skipped | Deliberate: an attempt that crashes must not spend a window |
| Forex: no OHLC data, no session/DST validator | Blocked on data and on not inventing a trading calendar |

None of these is a bypass to reserved ETH performance.