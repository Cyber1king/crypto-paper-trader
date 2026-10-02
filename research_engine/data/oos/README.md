# Out-of-Sample Data (`data/oos/`)

This directory holds **newly acquired** BTC/USDT hourly candles intended for
future out-of-sample validation of:

* the original baseline strategy, and
* the Phase 7 A2 configuration (`min_breakout_distance = 0.002`).

## Current status: POPULATED (Phase 10)

**Genuinely unseen BTC/USDT 1h data for 2026-01 through 2026-08 was acquired,
checksum-verified, normalised and validated.** See
`experiments/phase10/SUMMARY.md`.

| Item | Value |
|---|---|
| Source | Binance Vision, BTC/USDT **spot** klines, 1h, monthly archives |
| Months available | 2026-01 … 2026-08 (8 of 8 probed-and-present) |
| Months unavailable | 2026-09 … 2026-12 (HTTP 404; September's archive publishes on the first Monday of October) |
| Checksums | All 8 verified against the published `.CHECKSUM` |
| Combined dataset | `binance_spot_BTCUSDT_1h_202601-202608.csv` |
| Range | 2026-01-01 00:00 → 2026-08-31 23:00 |
| Candles | 5,832 |
| Missing hours | 0 |
| Duplicate timestamps | 0 |
| Invalid OHLC rows | 0 |
| Boundary vs research data | contiguous (exactly 1 hour after 2025-12-31 23:00) |
| Raw archives | `data/oos/raw/*.zip` with `.CHECKSUM` and `.provenance.txt` |

### Out-of-sample outcome (measured, not a claim)

Validation window 2026-01-03 00:00 → 2026-08-31 23:00 (5,784 bars, 48 warm-up
bars excluded), costs fee 0.001 + slippage 0.0005, risk fraction 0.01:

| Configuration | Trades | Net P&L | Win rate | PF | Max DD |
|---|---|---|---|---|---|
| baseline | 105 | **+$5.05** (+0.05%) | 34.29% | 1.0424 | 0.34% |
| A2 (`min_breakout_distance=0.002`) | 90 | **+$14.07** (+0.14%) | 36.67% | 1.1330 | 0.31% |

**Neither result is statistically distinguishable from zero.** The per-trade
95% confidence interval of the mean spans zero for both, before and after
costs. Both configurations were negative across 2024–2025. These figures do
not demonstrate a profitable strategy.

## Rules for this directory

1. **The original research dataset is not stored here and must never be
   written to.** `data/BTCUSDT_1h_Cleaned (1).csv` is the 2024-01-01 →
   2025-12-31 dataset used for all strategy research. `normalize_source()`
   refuses to write to it by name.
2. **New data must start after 2025-12-31 23:00.** Anything overlapping the
   research window is rejected, because it is not unseen.
3. **Accepted files use the project canonical layout** so the existing loader
   reads them unchanged:

   ```csv
   Date,Open,High,Low,Close,Volume
   01-01-2026 00:00,93500.00,94120.50,93210.00,93880.25,412.883
   ```

   `Date` is `dd-mm-yyyy HH:MM`, matching the research dataset exactly.
4. **Filename convention:** `<source>_<symbol>_<interval>_<YYYYMM>-<YYYYMM>.csv`
   for example `binance_spot_BTCUSDT_1h_202601-202609.csv`.
5. **Ship the provenance sidecar.** For every accepted file, keep a matching
   `<name>.provenance.txt` recording the source URL, the `.CHECKSUM` value if
   the source publishes one, the download date, and the SHA-256 of the
   downloaded file.

## How to add a file

1. Obtain the source file yourself. Phase 10 acquired data under explicit
   authorisation; any further acquisition needs its own authorisation.
2. Verify the published `.CHECKSUM` before normalising.
3. Run the acquisition tool, which validates and normalises, or call the
   library directly:

   ```python
   from crypto_paper_lab.acquisition import normalize_source, write_report

   report = normalize_source("downloaded.csv", "data/oos/accepted.csv")
   write_report(report, "data/oos/accepted.report.txt")
   assert report.accepted
   ```

4. If the report says `REJECTED`, do **not** use the data. Read the report,
   fix or re-fetch the source, and re-run. The tool never fills gaps,
   interpolates prices, or fabricates candles.

## Validation

Once a file is accepted here, the Phase 8 harness can consume it without any
change to strategy parameters:

```
python experiments/phase8/validation_harness.py data/oos/<file>.csv
```

The harness additionally re-checks contiguity, ordering, and that the first
eligible bar is strictly after 2025-12-31.
