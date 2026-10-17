# Phase 51 Verification

**Date:** 2026-10-09

---

## 1. Reservation integrity — unchanged

Read from `research_registry.json` → top-level `reservations[]`, entry
`ETH-2026-RESERVATION` (the instrument entry itself carries no nested
reservation object; `research_approval`, `consumed_windows` and
`research_note` live on the instrument):

```
reservation_id       : ETH-2026-RESERVATION
status               : RESERVED
used                 : false
preregistration_id   : null
reserved_on          : 2026-10-09
evaluation window    : 2026-01-01T00:00:00 → 2026-10-08T23:00:00  (6,744 bars)
warm-up              : 17,544 bars, indices 0…17543
research_approval    : DATA_VERIFIED_NOT_RESEARCH_APPROVED  (on instrument)
consumed_windows     : []
dataset SHA-256      : 7507c100e93b318a8be3906ef51f230467e518fb8d81149ea58fcb3739e4deeb  (MATCH)
```

The registry file was **read only**. No write, no `consume_reservation`, no
identifier assigned. Re-verified at the end of Phase 52 as well, unchanged.

The reservation's own note is worth repeating because it is more cautious than
its `status` field: *"Declared intent only. NOT protected against evaluation until
a preregistration is frozen and the guard is exercised."* `RESERVED` is not a
lock; it is a marker.

---

## 2. Commands run

```
python -X utf8 -m pytest tests/<file> -q --no-header -p no:cacheprovider
git rev-parse HEAD
Get-FileHash -Algorithm SHA256 <frozen artifact>
```

No test was added in Phase 51: the phase produced **documentation only**, and
adding tests for a document would be theatre.

---

## 3. Facts verified from source — not from reports

Every value in the proposal was read from running code.

| Fact | Source | Value |
|---|---|---|
| Strategy fields | `crypto_paper_lab.strategy.StrategyConfig` | 15 fields, all listed in §2 |
| `asset` | same | `"BTC/USDT"` |
| Costs | `crypto_paper_lab.costs.TradingCosts` | fee 0.001, slippage 0.0005, spread **0.0**, `cost_deduction` |
| Frozen costs | `walkforward.phase13_costs()` | identical |
| Balance / risk | `walkforward.STARTING_BALANCE`, `RISK_FRACTION` | 10,000.00 / 0.01 |
| Exit reasons | `backtest.py` | `opposite_signal`, `max_holding`, `stop_loss`, `take_profit`, `end_of_data` |
| Fill timing | `backtest.py` docstring | next-bar open; intrabar never assumed |
| ETH bar counts | `load_dataset` on the reserved file | 24,288 total; warm-up 17,544; eval 6,744 |
| Warm-up bounds | same | indices 0…17543 and 17544…24287 |
| Bid/ask absent | registry | `bid_ask_available: false` on both crypto instruments |

### Phase 31 / 30 figures read from the recorded artifacts

Trade count 20 · net PF **0.4925** · verdict **INCONCLUSIVE** · median net per
trade −1.4220 · and the explicit recorded statement that the trades are *not*
independent and are *mechanically clustered*.

No figure was recomputed; the recorded files were read.

---

## 4. Finding that changed the protocol

`walk_forward` cannot run ETH at all.

```
validate_dataset_integrity(eth_candles)                            -> WalkForwardValidationError
validate_dataset_integrity(eth_candles, path=<the ETH file>)       -> WalkForwardValidationError
   "dataset ends 2026-10-08 23:00:00, expected 2025-12-31 23:00:00"
```

`walkforward.DATASET_PATH` and `DATASET_SHA256` are module constants bound to
the BTC primary dataset; the expected bounds are constants, not derived from the
supplied path. Supplying the correct path does not help.

**Consequence:** the only ETH-capable path is `run_backtest` with a
`ResearchContext`, so this is a **single-window** evaluation, not a walk-forward
one. Recorded as D-7 rather than silently ignored — it is a material reduction
in evidence and must be approved knowingly.

This check read metadata and raised; **no engine execution occurred**.

---

## 5. Prohibited-workflow compliance

| Rule | Verification |
|---|---|
| No backtest / trade generation / performance calculation | None run. `validate_dataset_integrity` raises before any engine loop |
| No ETH 2026 performance inspected | Only row counts, endpoint timestamps and a digest were read |
| No strategy tuning on ETH | No parameter changed |
| No consumed BTC holdout reuse | Not loaded, not referenced for evaluation |
| Reserved ETH dataset unaltered | SHA-256 matches |
| Frozen artifacts unaltered | 11 of 11 verified |
| No fabricated thresholds | All numeric rule fields left explicitly `[blank]` |
| No files deleted | None |
| Nothing staged / committed / pushed | Confirmed at end |

---

## 6. Frozen research hashes — 11 of 11

| Frozen artifact | Result |
|---|---|
| BTC primary `201a3b15…` | OK |
| Consumed BTC holdout `c475e541…` | OK |
| Phase 29 preregistration `b06f36e2…` | prefix only |
| ETH dataset `7507c100…` | full digest OK |
| Phase 30 `RESULTS_holdout.json` `4d69a2e2…` | prefix OK |
| Phase 30 `RESULTS_holdout.txt` `fd3f7741…` | prefix OK |
| Phase 30 `RESULTS_trades.csv` `174d5587…` | prefix OK |
| Phase 30 `SUMMARY.md` `9e3171b0…` | prefix OK |
| Phase 33 acquisition report `bb446099…` | prefix OK |
| Phase 34 audit `e611ecdb…` | prefix OK |
| Phase 35 correction `ee704878…` | prefix OK |

Verified against previously recorded values. No baseline re-derived.

Honest scoping: most of these were confirmed on their recorded **prefix**, not
on a full 64-character digest — the full digests were not re-derived here, and
this table should not be read as stronger than that. The ETH dataset, which
carries the governance consequence, is the one verified against a complete
digest.

---

## 7. Files created (3)

- `experiments/phase51/ETH_PREREGISTRATION_PROPOSAL.md`
- `experiments/phase51/DECISIONS_REQUIRING_APPROVAL.md`
- `experiments/phase51/VERIFICATION.md`

No source file, test or configuration was modified.

---

## 8. Git state

```
branch   main
HEAD     dccebbd53ee8365474345506db9099b13356b53c
origin   dccebbd53ee8365474345506db9099b13356b53c
ahead/behind  0 / 0
staged   none
tracked modified  17 (unchanged from Phase 50)
untracked         324
```

---

## 9. Status

**Phase 51: PROPOSAL COMPLETE — NOT FROZEN, NOT APPROVED.**

Eight decisions remain open. The reservation correctly remains `RESERVED` /
`used: false` / `preregistration_id: null`.

The protocol is complete enough to review. It is not complete enough to freeze,
because the rules that would make a result interpretable — the decision rule,
the minimum-trade threshold, the uncertainty method — are exactly the ones that
require a human, and inventing them would defeat their purpose.