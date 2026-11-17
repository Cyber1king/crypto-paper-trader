import json, os
from pathlib import Path

# Find the registry file
registry_path = None
for root, dirs, files in os.walk(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader'):
    for f in files:
        if f == 'research_registry.json':
            registry_path = os.path.join(root, f)
            break
    if registry_path:
        break

if not registry_path:
    print('Registry not found')
    exit(1)

with open(registry_path, 'r') as f:
    REGISTRY = json.load(f)

INSTRUMENT_MAP = {}
for inst in REGISTRY.get("instruments", []):
    INSTRUMENT_MAP[inst["instrument_id"]] = inst

print(f'Loaded {len(INSTRUMENT_MAP)} instruments')

# Now modify the market_candles function in app.py
# Read the app.py file
app_path = r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\research_engine\\src\\paper_api\\app.py'
with open(app_path, 'r') as f:
    content = f.read()

# Find the market_candles function
old_func = '''    def market_candles(
        start: datetime | None = Query(
            default=None,
            description=(
                "Inclusive lower bound on bar time. Accepts a naive "
                "timestamp, which is read as UTC, or an offset-aware one, "
                "which is converted to UTC."
            ),
        ),
        end: datetime | None = Query(
            default=None,
            description="Inclusive upper bound on bar time. Same rules as start.",
        ),
        limit: int = Query(
            default=marketdata.DEFAULT_LIMIT,
            ge=1,
            le=marketdata.MAX_LIMIT,
            description=(
                f"Maximum candles to return, 1-{marketdata.MAX_LIMIT}. When "
                "more candles match, the most recent slice is returned."
            ),
        ),
    ) -> MarketResponse:'''

new_func = '''    def market_candles(
        start: datetime | None = Query(
            default=None,
            description=(
                "Inclusive lower bound on bar time. Accepts a naive "
                "timestamp, which is read as UTC, or an offset-aware one, "
                "which is converted to UTC."
            ),
        ),
        end: datetime | None = Query(
            default=None,
            description="Inclusive upper bound on bar time. Same rules as start.",
        ),
        limit: int = Query(
            default=marketdata.DEFAULT_LIMIT,
            ge=1,
            le=marketdata.MAX_LIMIT,
            description=(
                f"Maximum candles to return, 1-{marketdata.MAX_LIMIT}. When "
                "more candles match, the most recent slice is returned."
            ),
        ),
        instrument: str | None = Query(
            default=None, description="Instrument/market identifier. Omit for BTC/USDT."
        ),
    ) -> MarketResponse:'''

if old_func in content:
    content = content.replace(old_func, new_func)
    print('market_candles signature updated')
else:
    print('market_candles old string not found')

# Now modify the function body to use instrument
old_body = '''        if (
            start is not None
            and end is not None
            and marketdata.as_naive_utc(start) > marketdata.as_naive_utc(end)
        ):
            raise HTTPException(
                status_code=422,
                detail="start must be earlier than or equal to end",
            )

        candles = marketdata.load_research_candles()
        selected, truncated = marketdata.select_candles(
            candles, start, end, limit
        )'''

new_body = '''        if (
            start is not None
            and end is not None
            and marketdata.as_naive_utc(start) > marketdata.as_naive_utc(end)
        ):
            raise HTTPException(
                status_code=422,
                detail="start must be earlier than or equal to end",
            )

        # Load the correct dataset based on the instrument parameter
        dataset_path = None
        if instrument is not None:
            inst = INSTRUMENT_MAP.get(instrument)
            if inst is not None:
                dataset_path = inst.get("dataset_path")
        
        candles, _summary = marketdata.load_research_candles(dataset_path)
        selected, truncated = marketdata.select_candles(
            candles, start, end, limit
        )'''

if old_body in content:
    content = content.replace(old_body, new_body)
    print('market_candles body updated')
else:
    print('market_candles body old string not found')

with open(app_path, 'w') as f:
    f.write(content)
print('app.py modified')