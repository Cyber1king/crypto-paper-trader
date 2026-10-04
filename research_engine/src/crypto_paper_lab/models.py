from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Signal:
    timestamp: datetime
    side: Literal["long", "short", "flat"]
    reason: str
    price: float
    support: float
    resistance: float
    trend: Literal["up", "down", "sideways"]
    breakout: bool = False
    retest: bool = False

    # --- Phase 14B signal-time instrumentation -------------------------
    # Every field below is derived exclusively from the candles passed to
    # ``analyze()``. When the caller supplies ``candles[:index]`` these are
    # knowable strictly before the fill at ``candles[index].open``. None of
    # them participates in the signal decision; the gates in ``analyze`` are
    # unchanged. ``None`` means "not applicable for this signal", never a
    # substituted zero.

    #: Close of the signal candle, i.e. ``candles[-1]`` inside ``analyze``.
    #: Recorded separately because ``run_backtest`` overwrites ``price``
    #: with the next candle's open, which is a different value.
    signal_close: float | None = None

    #: Categorical trend already computed by ``indicators.trend``. Copied
    #: verbatim; the trend calculation itself is untouched.
    trend_state: Literal["up", "down", "sideways"] | None = None

    #: Signed distance by which the trigger candle closed beyond the broken
    #: level, as a fraction of that level. Positive means the level was
    #: exceeded upward for a long, downward for a short. For a retest entry
    #: this is measured on the candle that broke out; for a breakout entry,
    #: on the signal candle itself.
    breakout_distance: float | None = None

    #: Distance of the signal candle's wick from the retested level, as a
    #: fraction of that level. Recorded only for retest entries.
    retest_distance: float | None = None

    #: Trailing sample stdev of simple returns over ``StrategyConfig.lookback``
    #: periods, computed from the pre-signal candles. Not annualised.
    realised_volatility: float | None = None

    #: Mean high-low range over ``StrategyConfig.lookback`` trailing candles.
    #: A range proxy, not an ATR.
    mean_range: float | None = None


@dataclass
class PaperTrade:
    side: Literal["long", "short"]
    entry_time: datetime
    entry_price: float
    quantity: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    reason: str = ""
    costs: float = 0.0
    exit_reason: str = ""
    bars_held: int = 0

    #: Unadjusted reference prices as seen on the chart. Under the
    #: ``fill_price`` execution model these differ from ``entry_price`` and
    #: ``exit_price``, which record the prices actually paid or received.
    raw_entry_price: float | None = None
    raw_exit_price: float | None = None

    #: Execution friction broken out for reporting. ``costs`` is the amount
    #: actually deducted from the recorded gross P&L; under ``fill_price``
    #: the spread and slippage are already embedded in the fill prices and
    #: are therefore attributed here rather than deducted a second time.
    fee_total: float = 0.0
    slippage_total: float = 0.0
    spread_total: float = 0.0

    # --- Phase 14B entry-time instrumentation --------------------------
    # Copied from the triggering ``Signal`` at entry. All are ENTRY_TIME
    # features: derived only from candles available before the fill, never
    # from the exit, the trade outcome, MAE/MFE or any post-entry price.
    # ``None`` means the feature does not apply to this trade. These fields
    # are observational and are not read by any signal, sizing, exit or cost
    # calculation.

    signal_close: float | None = None
    trend_state: Literal["up", "down", "sideways"] | None = None
    breakout_distance: float | None = None
    retest_distance: float | None = None
    realised_volatility: float | None = None
    mean_range: float | None = None
    support_at_entry: float | None = None
    resistance_at_entry: float | None = None

    @property
    def pnl(self) -> float | None:
        """Return gross P&L at the recorded prices, before fees.

        Under ``cost_deduction`` the recorded prices are the raw chart
        prices, so this is gross before all friction. Under ``fill_price``
        the recorded prices already include spread and slippage, so this is
        gross before fees only. Use ``total_friction`` for the full cost.
        """

        if self.exit_price is None:
            return None

        direction = 1 if self.side == "long" else -1

        return (
            (self.exit_price - self.entry_price)
            * self.quantity
            * direction
        )

    @property
    def net_pnl(self) -> float | None:
        """Return P&L after the deducted portion of trading costs."""

        if self.pnl is None:
            return None

        return self.pnl - self.costs

    @property
    def total_friction(self) -> float | None:
        """Return all execution friction: fees plus spread plus slippage.

        This is the total cost of trading the position regardless of how the
        execution model distributes it between the fill price and ``costs``.
        """

        if self.net_pnl is None:
            return None

        return (
            self.fee_total + self.spread_total + self.slippage_total
        )
