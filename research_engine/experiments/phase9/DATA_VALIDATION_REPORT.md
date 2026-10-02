# Phase 9 — Data Validation Report

Date: 2026-10-01. Scope: validate the existing dataset and confirm the
project can safely accept new out-of-sample data.

## 1. The existing research dataset

`data/BTCUSDT_1h_Cleaned (1).csv`

| Property | Value |
|---|---|
| SHA-256 | `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B` |
| Size | 1,025,268 bytes |
| Lines | 17,545 (1 header + 17,544 data) |
| Header | `Date,Open,High,Low,Close,Volume` |
| Timestamp format | `dd-mm-yyyy HH:MM`, naive (no timezone) |
| Range | 2024-01-01 00:00 → 2025-12-31 23:00 |
| Candles | 17,544 |
| Duplicates | 0 |
| Non-increasing timestamps | 0 |
| Irregular gaps | 0 |
| Missing hours | 0 |
| `high < low` | 0 |
| `open` outside low–high | 0 |
| `close` outside low–high | 0 |
| Negative volume | 0 |
| Non-positive prices | 0 |
| `validate_dataset()` | PASS |
| Price range | 38,545.00 – 126,208.50 |

**Assessment: the dataset is internally clean and complete.** Contiguous
hourly coverage across both 2024 and 2025 with no gaps at all — including no
gap at the year boundary — and no OHLC violations.

### Unresolved provenance

**The origin of this file is not documented anywhere in the repository.** A
full-text search for a data source finds only `MARKET_DATA_API_KEY` (empty)
and a README sentence about a "future" adapter. Consequences:

- It is unknown whether the file came from Binance, Coinbase, Kraken, a paid
  vendor, or an export from a charting tool.
- It is unknown whether "Cleaned" means gaps were filled, outliers were
  trimmed, or only that a header was added.
- Vendor and exchange candles differ in construction, so a new dataset from a
  different venue may not be continuous with this one at the boundary.

This cannot be resolved from inside the repository. It is recorded here
rather than papered over, and it is a reason to treat any cross-source
comparison with caution.

## 2. Unseen-data availability

**No candles after 2025-12-31 exist in this repository.** Established in
Phase 8 by an exhaustive search of the working tree and all git commits.

## 3. Acquisition tooling validation

The new `crypto_paper_lab.acquisition` module was exercised end to end by
`experiments/phase9/acquisition_dry_run.py` using **synthetic fixtures in a
temporary directory**. No real market data was used and no download occurred.
Full output: `RESULTS_dry_run.txt`.

| Case | Fixture (synthetic) | Expected | Result |
|---|---|---|---|
| 1 | Binance layout, microsecond stamps, 720 contiguous hours | ACCEPT | **ACCEPT** |
| 2 | Binance layout, millisecond stamps, 240 hours | ACCEPT | **ACCEPT** |
| 3 | Binance layout with header row | ACCEPT | **ACCEPT** |
| 4 | Three missing hourly candles | REJECT | **REJECT** |
| 5 | Duplicate timestamp | REJECT | **REJECT** |
| 6 | `high` below `low` | REJECT | **REJECT** |
| 7 | Rows inside the 2024–2025 research window | REJECT | **REJECT** |
| 8 | Non-numeric field | REJECT | **REJECT** |
| 9 | Unrecognised column names | REJECT | **REJECT** |
| 10 | Attempt to write the protected dataset | REFUSE | **REFUSED** |

9/9 behaved as specified.

Case 8 illustrates a deliberate design choice: a structural parse failure
aborts the whole dataset rather than skipping the offending row, so partial
data is never mistaken for complete data. Case 4 reports the gap as
`2026-01-03 03:00 → 2026-01-03 06:00`, i.e. the interval that is absent,
not merely a count.

### Normalisation changes that were applied

When a dataset is accepted, the tool changes the *representation* only. It
records every change:

| Change | Why | Recorded in |
|---|---|---|
| Epoch → `dd-mm-yyyy HH:MM` | project canonical format | implied by format detection |
| Epoch unit inference (s/ms/µs/ns) | Binance spot switched to µs on 2025-01-01 | `notes` |
| Column subset to 6 fields | project canonical layout | `extra_columns` lists what was dropped |
| Numeric re-serialisation | canonical output | `output_sha256` |

**No price, volume, or timestamp value is altered.** Missing candles are never
filled, prices are never interpolated, and no candle is synthesised.

### Checksum handling

- **Source SHA-256** is computed and recorded in every report, giving
  tamper-evidence for what was supplied.
- **Vendor `.CHECKSUM` verification is not performed by this project.** The
  operator verifies it before parsing (see `ACQUISITION_PLAN.md` step 2) and
  records the published value in the provenance sidecar. This project does not
  fetch files, so it cannot fetch checksum files either.

## 4. Original dataset protection

Four independent measures:

1. **Named guard.** `normalize_source()` raises `AcquisitionError` if the
   output filename is `BTCUSDT_1h_Cleaned (1).csv`.
2. **No implicit writes.** The tool only ever writes to the explicit
   `output_path` the caller supplies.
3. **Read-only source.** Sources are opened `"r"`; a test asserts the source
   SHA-256 is unchanged after normalisation, and another asserts the real
   research dataset's SHA-256 is unchanged across a full acquisition run.
4. **Separate destination.** New data goes to `data/oos/`, which currently
   contains only a README.

Verified empirically in the dry run:

```
research dataset sha256 BEFORE: 201a3b15d50a791cb5be2b755107c8303906c8fc3ca6b64e8377c9fc73ba016b
research dataset sha256 AFTER : 201a3b15d50a791cb5be2b755107c8303906c8fc3ca6b64e8377c9fc73ba016b
UNCHANGED: True
```

## 5. Test coverage added

`tests/test_acquisition.py` — 27 tests, all fixtures synthetic and written to
`tmp_path`.

| Requirement | Test |
|---|---|
| Valid hourly data | `test_valid_binance_data_is_normalized`, `test_valid_native_data_round_trips` |
| Missing candles | `test_missing_candles_are_detected_and_rejected` |
| Duplicate timestamps | `test_duplicate_timestamps_are_detected_and_rejected` |
| Invalid OHLC relationships | `test_invalid_ohlc_relationship_is_rejected`, `test_open_outside_range_is_rejected` |
| Malformed input | `test_malformed_row_is_rejected`, `test_short_row_is_rejected` |
| Incorrect column names | `test_incorrect_column_names_are_rejected` |
| Negative volume / price | `test_negative_volume_is_rejected`, `test_non_positive_price_is_rejected` |
| Overlapping historical dates | `test_overlap_with_research_window_is_rejected` |
| Preservation of original dataset | `test_original_research_dataset_is_untouched`, `test_source_file_is_never_modified` |
| Correct normalized output | `test_valid_binance_data_is_normalized` (round-trips through `load_ohlcv_csv` + `validate_dataset`) |
| Rejection of invalid data | every rejection test asserts no output file exists |
| Dataset protection | `test_refuses_to_write_the_protected_dataset`, `test_refuses_identical_source_and_output` |
| Timestamp unit handling | `test_epoch_unit_detection`, `test_binance_microsecond_timestamps_parse` |
| Format detection | `test_detect_format`, `test_detect_format_rejects_unknown`, `test_detect_format_rejects_empty` |
| Hour alignment | `test_misaligned_timestamp_is_rejected` |
| Ordering | `test_out_of_order_rows_are_detected` |
| Reporting | `test_write_report_produces_readable_output` |

## 6. Bugs found and fixed during this phase

| Bug | Impact | Fix |
|---|---|---|
| `detect_format` rejected Binance files that carry a header row | Could not ingest a legitimate source layout | Recognise the `Open time` header; header rows are skipped, not the first data row |
| The first data row of a **headerless** file was consumed while probing for a header | **Would silently drop one candle from every Binance file** — the exact format recommended for acquisition | Peek with `itertools.chain` pushback so no data row is lost |
| `accepted` conflated "written" with "usable" | `strict=False` wrote a file while reporting `accepted=False`, which reads like a contradiction | Split into `accepted` (clean and usable) and `written` (file produced) |
| `summary_lines()` omitted errors | Console output could show `REJECTED` with no visible reason, since errors only reached the report file | Errors and the output path/SHA are now in the summary |

The second bug was the most serious: a one-candle silent loss would have
shifted every subsequent timestamp and produced a spurious "missing hour".
It was caught by a test asserting `candle_count == 50` on a 50-row file.

## 7. Current status

- Original dataset: **validated clean, protected, unchanged**.
- New out-of-sample data: **none acquired**. `data/oos/` contains only a README.
- Tooling: **built, tested (106 total tests passing), and demonstrated**.
- Strategy parameters: **unchanged**. Baseline and A2 both still reproduce
  exactly.
