#!/usr/bin/env python
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\crypto_paper_lab\dataset.py', 'r') as f:
    content = f.read()

# Add Forex validation after the MARKET_TYPES_SUPPORTED check
# The check is: if market_type is not None, and it's forex_spot, use the validator

insert_after = '''    if market_type is not None:
        from .researchguard import MARKET_TYPES_SUPPORTED

        if market_type not in MARKET_TYPES_SUPPORTED:
            raise ValueError(
                f"{MARKET_TYPE_UNSUPPORTED}: {market_type!r}. Supported here: "
                + ", ".join(sorted(MARKET_TYPES_SUPPORTED))
                + ". Refused rather than approximated."
            )'''

# The new code to insert
new_code = '''    if market_type is not None:
        from .researchguard import MARKET_TYPES_SUPPORTED

        if market_type not in MARKET_TYPES_SUPPORTED:
            raise ValueError(
                f"{MARKET_TYPE_UNSUPPORTED}: {market_type!r}. Supported here: "
                + ", ".join(sorted(MARKET_TYPES_SUPPORTED))
                + ". Refused rather than approximated."
        )

        # Forex spot validation: check that all candle timestamps are within
        # open market hours using the is_forex_market_open validator.
        if market_type == "forex_spot":
            from .forex_session import is_forex_market_open

            # Check each candle timestamp
            for candle in candles:
                if not is_forex_market_open(candle.timestamp):
                    raise ValueError(
                        f"Forex data contains out-of-session timestamp "
                        f"{candle.timestamp.isoformat()}. "
                        "Forex spot market is open Sunday 22:00 UTC through "
                        "Friday 22:00 UTC. Bar at this timestamp falls outside "
                        "the open window."
                    )'''

# Insert the new code
content = content.replace(insert_after, insert_after + '\n' + new_code)

# Write back
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\crypto_paper_lab\dataset.py', 'w') as f:
    f.write(content)

print('Added Forex validation to dataset.py')