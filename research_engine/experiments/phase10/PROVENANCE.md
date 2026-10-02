# Phase 10 — Provenance

Complete record of where the out-of-sample data came from and how it was
handled.

## Source

| Field | Value |
|---|---|
| Provider | Binance Vision (`data.binance.vision`) |
| Dataset type | Public market data, klines (candles) |
| Market | **BTC/USDT spot** — not futures, not a different pair |
| Interval | 1 hour |
| Distribution | Monthly zip archives |
| Account required | No |
| Base URL | `https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h` |
| Authorisation | Explicit user authorisation, Phase 10 |
| Retrieval date | 2026-10-01 |
| Mirror used | None — official source only |
| Licence | CC BY-NC-SA 4.0 + Binance Vision Dataset Terms (non-commercial) |

## Acquired items

8 monthly archives covering **2026-01 through 2026-08**. All preserved
byte-for-byte under `data/oos/raw/`:

| Archive | Bytes | Rows |
|---|---|---|
| `BTCUSDT-1h-2026-01.zip` | 43,807 | 744 |
| `BTCUSDT-1h-2026-02.zip` | 40,150 | 672 |
| `BTCUSDT-1h-2026-03.zip` | 44,392 | 744 |
| `BTCUSDT-1h-2026-04.zip` | 42,394 | 720 |
| `BTCUSDT-1h-2026-05.zip` | 43,547 | 744 |
| `BTCUSDT-1h-2026-06.zip` | 42,265 | 720 |
| `BTCUSDT-1h-2026-07.zip` | 43,238 | 744 |
| `BTCUSDT-1h-2026-08.zip` | 43,110 | 744 |

Companion `.CHECKSUM` and `.provenance.txt` files exist for each.

**Not acquired:** 2026-09, 2026-10, 2026-11, 2026-12 — all returned HTTP 404.
See `data/oos/raw/UNAVAILABLE_MONTHS.txt`.

## Verification chain

```
HTTP HEAD probe (existence)
      ↓
download .zip + .zip.CHECKSUM
      ↓
SHA-256 compare against published value      ← 8/8 verified, 0 failures
      ↓
extract raw CSV (preserved unmodified)
      ↓
crypto_paper_lab.acquisition.normalize_source(strict=True)
      ↓
per-month canonical CSV + validation report   ← 8/8 ACCEPTED
      ↓
merge (sort, duplicate scan, gap scan, boundary check)   ← 0 dupes, 0 gaps
      ↓
re-validate merged via normalize_source()      ← ACCEPTED
      ↓
load via load_ohlcv_csv() + validate_dataset() ← PASS
```

No stage bypassed the one above it. Checksums were verified **before** any
parsing, and re-verified on every run of `extract_and_normalise.py`.

## Provenance sidecars

One per archive at `data/oos/raw/BTCUSDT-1h-<YYYY-MM>.provenance.txt`,
recording source, official URL, checksum URL, filename, byte size, retrieval
date, published SHA-256, local SHA-256, verification status, covered range,
row count, first/last open times, parsing and normalisation notes, derived
file paths and digests, and the licence terms. Content shown in full for
2026-01 earlier in this phase.

These are **local records created by this project**, not documents issued by
Binance.

## Derived artefacts

| File | SHA-256 |
|---|---|
| `data/oos/binance_spot_BTCUSDT_1h_202601.csv` | `fc0afd05636ffc6a1fe930fc9394b50e1d3cfb0a869f0bea32d781fcea9bce6a` |
| `data/oos/binance_spot_BTCUSDT_1h_202602.csv` | `27a8d0912147d209b0fd7405ff935e88402371baf573b8892c583223f230555f` |
| `data/oos/binance_spot_BTCUSDT_1h_202603.csv` | `b65e9915443f92e9e3edf68e396f2e848ba07d88ff5a6a36048ecb0e2bf8164d` |
| `data/oos/binance_spot_BTCUSDT_1h_202604.csv` | `57c4d9bb110d68b7d173c76b2c0c7409e0b4f50a46cc320c59fcb44aa44d7586` |
| `data/oos/binance_spot_BTCUSDT_1h_202605.csv` | `725a47aaf2cc51124ac0bc27697222d266577642cc927473cfbe6c65af9b5afc` |
| `data/oos/binance_spot_BTCUSDT_1h_202606.csv` | `eaf631e76978149d464618269b58f5daae5d40e39b507a6eba94b96f43cce3b0` |
| `data/oos/binance_spot_BTCUSDT_1h_202607.csv` | `9d46773a798094b1ec9f7b89025bfd609039cf5bf4c2be6eb1c767e93c48352a` |
| `data/oos/binance_spot_BTCUSDT_1h_202608.csv` | `ae4edd83667f99b0f5c80f083f6868bf75a004a024ad80e6d5ba90d7c05a776e` |
| `data/oos/binance_spot_BTCUSDT_1h_202601-202608.csv` | `918153fde98e39c03eef8a7b82a2861adfdc98a080c8810e371869eb3ea22437` |

## Transformation record

Normalisation changed **representation only**:

| Transformation | Rationale |
|---|---|
| Epoch microseconds → `dd-mm-yyyy HH:MM` | Project canonical timestamp format |
| 12 source columns → 6 canonical columns | `Date,Open,High,Low,Close,Volume` |
| Numeric re-serialisation | Canonical output formatting |

**Unchanged:** every open, high, low, close and volume value; every
timestamp instant.

**Never performed:** gap filling, price interpolation, outlier smoothing,
candle synthesis, deduplication by deletion, or reordering beyond a stable
sort. A rejected month would have been preserved with its report and
explained; in the event all 8 months were accepted.

## Original dataset

`data/BTCUSDT_1h_Cleaned (1).csv` — **not modified, not merged into, not
truncated**. SHA-256 before and after Phase 10:

```
201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B
```

The new data lives only in `data/oos/`. `normalize_source()` refuses by name
to write the protected dataset, and a test pins its digest.

## Outstanding provenance gap

**The origin of the 2024–2025 dataset is still undocumented.** No source,
URL, venue or acquisition date is recorded anywhere in the repository
(recorded in `experiments/phase9/DATA_VALIDATION_REPORT.md`). Consequently it
is **not established** that the Binance 2026 spot candles are constructed the
same way as that file. Timestamps join seamlessly, but continuity of
*construction* is assumed rather than demonstrated.

This gap cannot be closed retrospectively. It should temper any comparison
that spans the 2025/2026 boundary, and it is a reason to prefer validating
against the 2026 data alone rather than splicing it onto the older file.
