from datetime import datetime

from .costs import FILL_PRICE, TradingCosts
from .models import PaperTrade, Signal


class PaperBroker:
    """In-memory simulator with configurable paper-trading costs.

    Two execution models are supported, selected by
    ``TradingCosts.execution_model``.

    ``cost_deduction`` (default, legacy Phase 5-11)
        ``entry_price`` and ``exit_price`` record the raw reference price
        exactly as it appears on the chart. Fees and slippage are deducted
        from P&L afterwards in a single ``costs`` figure. This reproduces
        every previously recorded research result.

    ``fill_price`` (Phase 12)
        Spread and slippage are applied to the fill price itself, so
        ``entry_price`` and ``exit_price`` are the prices actually paid or
        received. Position size is derived from the real entry fill and fees
        are charged on filled notional. ``costs`` then holds fees only,
        because spread and slippage are already inside the recorded prices;
        they are reported via ``spread_total`` / ``slippage_total`` instead
        of being deducted a second time.

    Both models charge spread and slippage adversely on every leg, so a long
    buys above and sells below the reference while a short sells below and
    buys back above. Both are fully deterministic.
    """

    def __init__(
        self,
        starting_balance: float = 10_000.0,
        costs: TradingCosts | None = None,
    ) -> None:
        if starting_balance <= 0:
            raise ValueError("starting balance must be positive")

        self.starting_balance = starting_balance
        self.cash = starting_balance
        self.costs = costs or TradingCosts()
        self.open_trade: PaperTrade | None = None
        self.journal: list[PaperTrade] = []

    def _fill_price(
        self,
        reference: float,
        side: str,
        entering: bool,
    ) -> float:
        """Return the fill price for one leg.

        ``entering`` selects which side of the book the trade crosses.
        Opening a long and closing a long sell, so the two directions are
        exact opposites. Returns ``reference`` unchanged under
        ``cost_deduction``.
        """

        if self.costs.execution_model != FILL_PRICE:
            return reference

        is_buy = (side == "long") == entering
        sign = 1.0 if is_buy else -1.0

        return reference * (
            1.0 + sign * self.costs.adverse_rate
        )

    def open_from_signal(
        self,
        signal: Signal,
        risk_fraction: float = 0.01,
    ) -> PaperTrade:
        if signal.side == "flat":
            raise ValueError("flat signals cannot open a paper trade")

        if self.open_trade:
            raise ValueError("a paper trade is already open")

        if not 0 < risk_fraction <= 1:
            raise ValueError("risk_fraction must be between 0 and 1")

        reference = signal.price
        fill = self._fill_price(
            reference,
            signal.side,
            entering=True,
        )

        quantity = (self.cash * risk_fraction) / fill

        # Phase 14B: copy the ENTRY_TIME signal features onto the trade so
        # they survive independently of the Signal object. ``support`` and
        # ``resistance`` are the levels the signal was judged against, taken
        # from the pre-signal candles. None of these fields is read by any
        # sizing, exit or cost calculation.
        self.open_trade = PaperTrade(
            side=signal.side,
            entry_time=signal.timestamp,
            entry_price=fill,
            quantity=quantity,
            reason=signal.reason,
            raw_entry_price=reference,
            signal_close=signal.signal_close,
            trend_state=signal.trend_state,
            breakout_distance=signal.breakout_distance,
            retest_distance=signal.retest_distance,
            realised_volatility=signal.realised_volatility,
            mean_range=signal.mean_range,
            support_at_entry=signal.support,
            resistance_at_entry=signal.resistance,
        )

        return self.open_trade

    def close(
        self,
        price: float,
        timestamp: datetime,
    ) -> PaperTrade:
        if not self.open_trade:
            raise ValueError("no paper trade is open")

        trade = self.open_trade

        # Invariant: fill_price attributes spread and slippage against the
        # raw reference notional, so the raw entry reference must be present.
        # Substituting a silent zero here would halve the reported friction
        # without any error, so refuse instead. The check is scoped to
        # fill_price because cost_deduction never reads these fields and
        # legacy trades constructed without them must keep working.
        if (
            self.costs.execution_model == FILL_PRICE
            and trade.raw_entry_price is None
        ):
            raise ValueError(
                "raw_entry_price is required to attribute spread and "
                "slippage under execution_model='fill_price'; open the "
                "trade with PaperBroker.open_from_signal or set "
                "raw_entry_price explicitly"
            )

        reference = price
        fill = self._fill_price(
            reference,
            trade.side,
            entering=False,
        )

        trade.exit_price = fill
        trade.exit_time = timestamp
        trade.raw_exit_price = reference

        entry_value = trade.entry_price * trade.quantity
        exit_value = trade.exit_price * trade.quantity

        # Fees are always charged on the notional actually transacted.
        trade.fee_total = (
            entry_value + exit_value
        ) * self.costs.fee_rate

        if self.costs.execution_model == FILL_PRICE:
            # Spread and slippage are already inside the fill prices. Attribute
            # them against the raw reference notional purely for reporting, and
            # do NOT deduct them again or the cost would be charged twice.
            # raw_entry_price is guaranteed non-None by the check in close().
            raw_entry = trade.raw_entry_price * trade.quantity
            raw_exit = (trade.raw_exit_price or 0.0) * trade.quantity
            raw_notional = raw_entry + raw_exit

            trade.spread_total = (
                raw_notional * self.costs.spread_rate
            )
            trade.slippage_total = (
                raw_notional * self.costs.slippage_rate
            )
            trade.costs = trade.fee_total
        else:
            # Legacy: fills equal the raw reference, so raw and filled
            # notional coincide and slippage is deducted outright.
            notional = entry_value + exit_value

            trade.spread_total = 0.0
            trade.slippage_total = (
                notional * self.costs.slippage_rate
            )
            trade.costs = trade.fee_total + trade.slippage_total

        self.cash += trade.net_pnl or 0.0

        self.journal.append(trade)
        self.open_trade = None

        return trade
