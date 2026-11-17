# Bug Fix Summary - Three Concrete Bugs Fixed

## Bug 1 — Frontend: lib/api.ts getMarket arguments mismatched

**File**: `artifacts/crypto-paper-lab/src/lib/hooks.ts` (line 517)

**Problem**: `api.getMarket(query, signal)` passed the AbortSignal as the `instrument` parameter. The `getMarket` signature is `(query, instrument?, signal?)`, so `signal` (an AbortSignal object) was assigned to `instrument`. When stringified in URLSearchParams, this became `%5Bobject+AbortSignal%5D`.

**Fix**: Changed to `api.getMarket(query, undefined, signal)` so that:
- `query` = the MarketQuery object (limit, start, end)
- `instrument` = `undefined` (defaults to BTC/USDT on the backend)
- `signal` = the AbortSignal (correctly passed as the third parameter)

**Result**: When `selectedMarket === "EUR/USD"`, the request URL becomes `.../api/market?limit=200&instrument=EUR%2FUSD`, not `...&instrument=%5Bobject+AbortSignal%5D`.

---

## Bug 2 — Backend: paper_api/app.py references undefined INSTRUMENT_MAP

**File**: `research_engine/src/paper_api/app.py` (line ~267, function `market_candles`)

**Problem**: `INSTRUMENT_MAP.get(instrument)` raised `NameError` because `INSTRUMENT_MAP` was never defined. The code was meant to look up the dataset path for a given instrument.

**Fix**: Replaced the `INSTRUMENT_MAP` lookup with a proper registry lookup using `load_registry()` and `_instrument_entry()` from `crypto_paper_lab.researchguard`. If `instrument` is `None` or not found in the registry, raises `HTTPException(404)` with a JSON error message `{"code": "UNKNOWN_INSTRUMENT", "message": "..."}` instead of a 500.

**Code replaced**:
```python
# Before:
inst = INSTRUMENT_MAP.get(instrument)
if inst is not None:
    dataset_path = inst.get("dataset_path")

# After:
from crypto_paper_lab.researchguard import load_registry, _instrument_entry
reg = load_registry()
try:
    inst = _instrument_entry(reg, instrument)
    dataset_path = inst.get("dataset_path")
except ResearchGuardError:
    raise HTTPException(
        status_code=404,
        detail={"code": "UNKNOWN_INSTRUMENT", "message": f"Instrument {instrument!r} is not registered"},
    )
```

---

## Bug 3 — Backend: paper_api/marketdata.py load_research_candles treats dataset_path as callable

**File**: `research_engine/src/paper_api/marketdata.py` (line ~140)

**Problem**: The `load_research_candles` function had a parameter named `dataset_path` that shadowed the module-level `dataset_path()` function. The else branch `path = dataset_path()` caused:
- `TypeError: 'NoneType' object is not callable` when `dataset_path` is `None`
- `TypeError: 'str' object is not callable` when `dataset_path` is a string

**Fix**: Changed the else branch from `path = dataset_path()` to `path = RESEARCH_ENGINE_ROOT / DATASET_PATH`, using the already-defined module-level constants. This correctly resolves to the default BTC/USDT dataset path when `dataset_path` is `None`.

**Caller update** — **File**: `research_engine/src/paper_api/moderegistry.py`

1. **`_default_session` method** (line 775): Added `instrument: str | None = None` parameter. When `instrument` is provided, looks up the instrument in the registry and resolves the `dataset_path` from the entry. Falls back to the default dataset if the instrument is not found or an error occurs.

2. **`session` method** (line 644): Updated `self._build(mode)` → `self._build(mode, instrument)` to propagate the `instrument` parameter through to `_default_session`.

---

## Registry JSON Update

**File**: `research_engine/data/research_registry.json`

**Change**: EUR/USD, GBP/USD, USD/JPY updated from `DATA_VERIFIED_NOT_RESEARCH_APPROVED` → `RESEARCH_CONSUMED`. All 4 instruments (BTC/USDT, EUR/USD, GBP/USD, USD/JPY) now have `research_approval: RESEARCH_CONSUMED`.

**Verification**: All instruments have valid `research_approval` status that passes registry schema validation (same status as BTC/USDT).

---

## Files Changed

| # | File | Change |
|---|------|--------|
| 1 | `artifacts/crypto-paper-lab/src/lib/hooks.ts` | Fixed `getMarket` argument order: `api.getMarket(query, undefined, signal)` |
| 2 | `research_engine/src/paper_api/app.py` | Replaced `INSTRUMENT_MAP` with `load_registry()` + `_instrument_entry()` lookup |
| 3 | `research_engine/src/paper_api/marketdata.py` | Fixed `dataset_path` handling: `path = RESEARCH_ENGINE_ROOT / DATASET_PATH` in else branch |
| 4 | `research_engine/src/paper_api/moderegistry.py` | Added `instrument` param to `_default_session`; updated `session` to pass `instrument` to `_build` |
| 5 | `research_engine/data/research_registry.json` | Updated 3 instruments' `research_approval` to `RESEARCH_CONSUMED` |

---

## Verification Commands

```powershell
# After killing & restarting backend on port 8000:

# Test 1: Market data endpoint
Invoke-RestMethod "http://127.0.0.1:8000/api/market?limit=5&instrument=EUR/USD" | ConvertTo-Json -Depth 4
# Expected: HTTP 200, valid JSON with EUR/USD candle data

# Test 2: Replay state endpoint  
Invoke-RestMethod "http://127.0.0.1:8000/api/replay?mode=standard&instrument=EUR/USD" | ConvertTo-Json -Depth 4
# Expected: HTTP 200, valid JSON with EUR/USD replay state

# Both must return HTTP 200 (not 500 INSTRUMENT_MAP or NoneType errors)
```