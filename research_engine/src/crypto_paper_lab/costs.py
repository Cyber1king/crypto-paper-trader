from dataclasses import dataclass


@dataclass(frozen=True)
class TradingCosts:
    """Configurable costs for paper-trading research."""

    fee_rate: float = 0.001
    slippage_rate: float = 0.0005

    def __post_init__(self) -> None:
        if self.fee_rate < 0:
            raise ValueError("fee_rate cannot be negative")

        if self.slippage_rate < 0:
            raise ValueError("slippage_rate cannot be negative")
