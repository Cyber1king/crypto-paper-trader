# Phase 9 — Data Source Review

**Reviewed:** 2026-10-01. No market data was downloaded. No account was
created or used. Findings below come from reading official vendor
documentation, and each is labelled with what was actually verified.

## What the repository already documents

Essentially nothing. Searching the whole repository for a data source turns up
only a placeholder:

| Location | Content |
|---|---|
| `research_engine/.env.example` | `MARKET_DATA_API_KEY=` (empty) with the comment "Optional key for a future public market-data provider" |
| `research_engine/README.md` | "A future public market-data adapter **may** use `MARKET_DATA_API_KEY`, but the system must never accept exchange trading credentials." |
| `research_engine/src/crypto_paper_lab/data.py` | `optional_market_data_key()` reads that env var and is never called |

**There is no documented source, no URL, and no provenance for the existing
2024–2025 dataset.** This is an unresolved gap recorded in
`DATA_VALIDATION_REPORT.md`. The origin of
`BTCUSDT_1h_Cleaned (1).csv` is unknown; only its content is known.

## Source candidates

### 1. Binance Vision — `data.binance.vision` (RECOMMENDED)

Verified from the official repository README
(`github.com/binance/binance-public-data`) and the Terms and Conditions file.

| Property | Status |
|---|---|
| BTC/USDT hourly candles | **Verified.** Spot klines are published for all symbols; `1h` is an explicitly listed interval. |
| Data after Dec 2025 | **Verified available.** Daily files appear the next day; monthly files on the first Monday of the month. |
| URL pattern | **Verified.** `https://data.binance.vision/data/spot/monthly/klines/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{YYYY}-{MM}.zip` |
| Timestamps | **Verified, and a trap.** Spot timestamps are epoch integers in **microseconds from 2025-01-01 onward** and milliseconds before. |
| OHLCV fields | **Verified.** Spot kline columns: `Open time, Open, High, Low, Close, Volume, Close time, Quote asset volume, Number of trades, Taker buy base asset volume, Taker buy quote asset volume, Ignore`. |
| Account required | **Verified.** Public download, no account or API key. |
| Integrity metadata | **Verified.** Every zip has a sibling `.CHECKSUM` file verified with `sha256sum -c`. |
| Licence | **Verified.** MIT for the tooling; the **data** is CC BY-NC-SA 4.0 plus the Binance Vision Dataset Terms. |
| Usage restrictions | **Verified.** Non-commercial only. Clause 4.1 explicitly permits "academic research, non-monetized open educational projects, algorithmic historical backtesting for purely personal non-production research". Live order execution and signal redistribution are prohibited. |
| Rate limits | **Verified.** Clause 7.1–7.2 requires obeying posted rate limits; scraping or circumventing them is prohibited and may result in IP bans. |
| Archive stability | **Verified caveat.** The README states "Archived files **may be updated** at a later date as a result of recently discovered issues" and publishes a changelog of such revisions. |

**Why it fits:** it is the only candidate offering the exact instrument
(BTC/USDT), the exact interval (1h), bulk files rather than paging, and
published checksums.

**The revision caveat matters.** Because Binance has corrected archived
files in the past, and because the existing 2024–2025 CSV's provenance is
unknown, a 2026 file fetched from Binance is **not guaranteed to be
methodologically continuous** with the existing dataset. This cannot be
resolved without knowing the original source. It is a reason to treat
cross-boundary comparisons with care, not a reason to reject the source.

### 2. Coinbase Exchange — `api.exchange.coinbase.com`

| Property | Status |
|---|---|
| Hourly candles | **Verified.** `granularity` accepts `3600`. |
| Account required | **Verified.** Public market-data endpoint, no API key. |
| Instrument | **Mismatch.** Product is `BTC-USD`, not BTC/USDT. A different pair and a different quote currency. |
| Volume field | **Verified.** Candle array is `[time, low, high, open, close, volume]`. |
| Timestamps | **Verified.** Unix epoch **seconds**; field order is low/high/open/close, not OHLC. Responses may arrive newest-first. |
| Bulk archive | **Verified absent.** No bulk file archive; histories must be paged. |
| Page size | **Verified.** Maximum **300 candles** per request — about 12.5 days at 1h. |
| Data completeness | **Verified caveat.** Docs state "Historical rate data may be incomplete. No data is published for intervals where there are no ticks." |

**Assessment:** usable but inferior. Different instrument, 300-candle paging,
no checksums, and an explicit incompleteness warning. Gap handling matters
because the acquisition tool rejects missing hours.

### 3. Kraken — `api.kraken.com`

| Property | Status |
|---|---|
| Hourly candles | **Verified.** `interval=60`. |
| Account required | **Verified.** `/0/public/OHLC` is unauthenticated. |
| Instrument | **Mismatch.** `XBTUSD`, not BTC/USDT. |
| Page size | **Verified.** Maximum **720 candles** per call — about 30 days at 1h. |
| Checksums | **Not verified.** None documented. |
| Rate limits | **Verified.** Public endpoints rate-limited per IP; recommended ≥1 s between OHLC calls. |
| History depth | **Verified caveat.** Docs state the OHLC endpoint returns only a limited window (720 points of the requested interval) and that it does not offer websocket replay history for years. |

**Assessment:** poor fit. Wrong instrument, small page size, no integrity
metadata, and explicitly limited lookback depth.

### 4. Binance REST API (`api/v3/klines`) instead of bulk files

Mentioned because it is the upstream of the bulk files. **Not evaluated in
depth and not recommended for this purpose:** it needs API keys, is
rate-limited per weight, and returns at most 1000 rows per call. The bulk
archive already exists for exactly this use case.

## Comparison summary

| Criterion | Binance Vision | Coinbase | Kraken |
|---|---|---|---|
| Exact pair BTC/USDT | **Yes** | No (BTC-USD) | No (XBTUSD) |
| Native 1h interval | **Yes** | Yes | Yes |
| Bulk files | **Yes** (daily + monthly) | No | No |
| No account needed | **Yes** | Yes | Yes |
| Published checksums | **Yes** (`.CHECKSUM`) | Not verified | Not verified |
| Candles per request | Whole file | 300 | 720 |
| Explicit non-commercial research use | **Yes** | Not verified | Not verified |
| Archive may be revised | **Yes (disclosed)** | Not verified | Not verified |
| Data completeness warning | Not stated | **Yes** | Not verified |

## Recommendation

**Binance Vision bulk monthly archives**, subject to explicit authorisation
to download, verification of the published `.CHECKSUM` before use, and
acceptance of the CC BY-NC-SA 4.0 non-commercial terms, which permit this
project's educational paper-trading research.

## Limits of this review

- Every claim above comes from vendor documentation read on 2026-10-01. I did
  not download a single file, so I have **not** verified that any specific
  2026 monthly archive actually exists, nor its real size, nor its real
  content, nor that its checksum matches.
- Terms, endpoints, and archive layouts change. Re-verify before relying on
  any of this at acquisition time.
- I have not assessed CryptoCompare, CoinGecko, Kaiko, Amberdata, Tardis, or
  any paid vendor. Several require an account or paid plan, which conflicts
  with the no-account constraint, but that was not tested.
