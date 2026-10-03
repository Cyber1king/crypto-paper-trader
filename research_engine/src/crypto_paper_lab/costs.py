from dataclasses import dataclass
from typing import Literal

#: Fills are recorded at the raw market price and fees plus slippage are
#: deducted from P&L afterwards. This is the legacy Phase 5-11 model and
#: remains the default so that every previously recorded research result
#: reproduces exactly.
COST_DEDUCTION = "cost_deduction"

#: Spread and slippage are applied to the fill price itself. The recorded
#: entry/exit prices are the prices actually paid or received.
FILL_PRICE = "fill_price"


@dataclass(frozen=True)
class TradingCosts:
    """Configurable costs for paper-trading research.

    Parameters
    ----------
    fee_rate:
        Proportional trading fee charged once on each filled notional, so a
        round trip pays ``fee_rate`` twice in total.
    slippage_rate:
        Proportional adverse price movement applied to each leg. It models
        size and latency effects: you buy slightly above the reference and
        sell slightly below it.
    spread_rate:
        Proportional half-spread applied to each leg, kept separate from
        ``slippage_rate`` so that crossing the bid-ask spread can be
        reported independently of size/latency slippage. Requires
        ``execution_model="fill_price"``; under ``"cost_deduction"`` the
        spread is indistinguishable from slippage and charging both would
        double count, so it is rejected.
    execution_model:
        ``"cost_deduction"`` (default) keeps fills at the raw reference price
        and deducts fees plus slippage from P&L afterwards.
        ``"fill_price"`` applies spread and slippage to the fill price,
        derives position size from the real entry fill, and charges fees on
        filled notional.

    Notes
    -----
    Both models are deterministic and use no randomness.

    The two models are only *approximately* equivalent in P&L at matching
    rates; they are not mathematically identical. Two effects separate them.
    First, ``fill_price`` derives position size from the slipped entry fill
    rather than the raw reference price, so it holds marginally fewer units
    on a long and marginally more on a short. Second, it charges fees on the
    notional actually transacted rather than on the raw reference notional.
    For the default 0.05% slippage these effects are around 5e-4 relative,
    not negligible at the fourth decimal place, and they grow with the
    configured rates. Use one model consistently when comparing runs.
    """

    fee_rate: float = 0.001
    slippage_rate: float = 0.0005
    spread_rate: float = 0.0
    execution_model: Literal["cost_deduction", "fill_price"] = COST_DEDUCTION

    def __post_init__(self) -> None:
        if self.fee_rate < 0:
            raise ValueError("fee_rate cannot be negative")

        if self.slippage_rate < 0:
            raise ValueError("slippage_rate cannot be negative")

        if self.spread_rate < 0:
            raise ValueError("spread_rate cannot be negative")

        if self.execution_model not in (COST_DEDUCTION, FILL_PRICE):
            raise ValueError(
                f"unknown execution_model: {self.execution_model!r}"
            )

        if self.spread_rate > 0 and self.execution_model == COST_DEDUCTION:
            raise ValueError(
                "spread_rate requires execution_model='fill_price'; under "
                "'cost_deduction' the spread cannot be separated from "
                "slippage and charging both would double count"
            )

    @property
    def adverse_rate(self) -> float:
        """Total proportional adverse move applied to each leg."""

        return self.spread_rate + self.slippage_rate
