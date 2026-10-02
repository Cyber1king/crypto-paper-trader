# Phase 10 — Download Report

Date of retrieval: **2026-10-01**
Source: **Binance Vision** official public archive
Authorisation: explicit user authorisation for BTC/USDT spot hourly data
from 2026-01-01.

## Source parameters

| Parameter | Value |
|---|---|
| Market | BTC/USDT **spot** (not futures) |
| Data type | klines (candles) |
| Interval | 1 hour |
| Base URL | `https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h` |
| Archive pattern | `BTCUSDT-1h-YYYY-MM.zip` |

No third-party mirror was used. No futures data was downloaded. No other
trading pair was downloaded.

## Availability probe

Every month of 2026 was probed with an HTTP `HEAD` request **before**
downloading. Availability was not inferred from the URL pattern.

| Month | HTTP status | Outcome |
|---|---|---|
| 2026-01 | 200 | available, downloaded |
| 2026-02 | 200 | available, downloaded |
| 2026-03 | 200 | available, downloaded |
| 2026-04 | 200 | available, downloaded |
| 2026-05 | 200 | available, downloaded |
| 2026-06 | 200 | available, downloaded |
| 2026-07 | 200 | available, downloaded |
| 2026-08 | 200 | available, downloaded |
| 2026-09 | **404** | **unavailable — not downloaded** |
| 2026-10 | **404** | **unavailable — not downloaded** |
| 2026-11 | **404** | **unavailable — not downloaded** |
| 2026-12 | **404** | **unavailable — not downloaded** |

### Why 2026-09 onward is unavailable

Binance Vision publishes a monthly archive on the **first Monday of the
following month**. On the retrieval date (2026-10-01, a Thursday) the first
Monday of October 2026 was 2026-10-05, which had not yet occurred. The
September 2026 monthly archive was therefore not published. October 2026 was
still in progress, and November and December 2026 lie in the future.

**No daily archives were substituted.** A complete-month requirement was
respected: no partial or in-progress month was treated as complete.

## Downloaded archives

| Month | Archive | Bytes | Rows in CSV |
|---|---|---|---|
| 2026-01 | `BTCUSDT-1h-2026-01.zip` | 43,807 | 744 |
| 2026-02 | `BTCUSDT-1h-2026-02.zip` | 40,150 | 672 |
| 2026-03 | `BTCUSDT-1h-2026-03.zip` | 44,392 | 744 |
| 2026-04 | `BTCUSDT-1h-2026-04.zip` | 42,394 | 720 |
| 2026-05 | `BTCUSDT-1h-2026-05.zip` | 43,547 | 744 |
| 2026-06 | `BTCUSDT-1h-2026-06.zip` | 42,265 | 720 |
| 2026-07 | `BTCUSDT-1h-2026-07.zip` | 43,238 | 744 |
| 2026-08 | `BTCUSDT-1h-2026-08.zip` | 43,110 | 744 |
| | **Total** | **342,903** | **5,832** |

Each month's row count equals the exact number of hours in that month,
which independently confirms the archives are complete:

| Month | Days | Expected hours | Received |
|---|---|---|---|
| 2026-01 | 31 | 744 | 744 ✅ |
| 2026-02 | 28 (not a leap year) | 672 | 672 ✅ |
| 2026-03 | 31 | 744 | 744 ✅ |
| 2026-04 | 30 | 720 | 720 ✅ |
| 2026-05 | 31 | 744 | 744 ✅ |
| 2026-06 | 30 | 720 | 720 ✅ |
| 2026-07 | 31 | 744 | 744 ✅ |
| 2026-08 | 31 | 744 | 744 ✅ |

## Raw archive preservation

All downloaded archives, their `.CHECKSUM` files, and per-archive
provenance sidecars are preserved under `data/oos/raw/`:

```
data/oos/raw/
  BTCUSDT-1h-2026-01.zip
  BTCUSDT-1h-2026-01.zip.CHECKSUM
  BTCUSDT-1h-2026-01.provenance.txt
  ... (through 2026-08)
  UNAVAILABLE_MONTHS.txt
  extracted/                       <- extracted raw CSVs, unmodified
```

No existing file was overwritten. The `data/oos/` directory did not exist
before Phase 9.

## Rejections

**None.** No archive was rejected for a checksum mismatch, a parse failure,
or a validation failure. All 8 downloaded months were accepted.

## Commands used

```
# availability probe
curl.exe -s -o NUL -w "%{http_code}" -I \
  "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-MM.zip"

# download
curl.exe -s -f -o "data/oos/raw/BTCUSDT-1h-2026-MM.zip"      "$BASE/$F"
curl.exe -s -f -o "data/oos/raw/BTCUSDT-1h-2026-MM.zip.CHECKSUM" "$BASE/$F.CHECKSUM"

# verification and processing (project tooling)
python experiments/phase10/extract_and_normalise.py
python experiments/phase10/merge_and_check.py
python experiments/phase10/write_provenance.py
python experiments/phase8/validation_harness.py data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv
python experiments/phase10/oos_interpretation.py
```

## Original dataset

`data/BTCUSDT_1h_Cleaned (1).csv` was **not modified**. SHA-256 before and
after every step:

```
201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B
```
