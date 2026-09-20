# Crypto Paper Lab — Python Research Engine

A small, dependency-light foundation for learning about BTC/USDT market analysis and paper-trading strategy research.

> **Paper trading only.** This package has no exchange account integration, no authenticated trading client, and no order execution or financial transaction capability. Signals and trades are simulations, not financial advice.

## Included

- Historical OHLCV CSV loading
- Simple moving-average trend detection
- Rolling support and resistance
- Breakout and retest signal logic
- In-memory paper trade simulation and journal
- Win rate, net P&L, average P&L, and profit factor
- Configurable asset, timeframe, lookback, and strategy thresholds
- Unit tests for core strategy and simulator behavior

## Data format

Provide a CSV with these headers:

```csv
timestamp,open,high,low,close,volume
2026-01-01T00:00:00+00:00,93000,93500,92500,93200,125.4
```

`load_ohlcv_csv()` reads local historical data. A future public market-data adapter may use `MARKET_DATA_API_KEY`, but the system must never accept exchange trading credentials.

## Setup

```bash
cd research_engine
python -m pip install -e ".[dev]"
cp .env.example .env
pytest
```

Keep `.env` out of version control. Never print API keys or commit them to source.

## Example

```python
from crypto_paper_lab.data import load_ohlcv_csv
from crypto_paper_lab.strategy import StrategyConfig, analyze

candles = load_ohlcv_csv("data/btc_usdt_1h.csv")
signal = analyze(candles, StrategyConfig(asset="BTC/USDT", timeframe="1h"))
print(signal)
```

## Scope

The initial version intentionally avoids live feeds, databases, optimization frameworks, machine learning, leverage, and exchange connectivity. Those are not required to study deterministic strategy logic safely.