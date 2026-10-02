
from collections.abc import Sequence
from dataclasses import replace

from .costs import TradingCosts
from .models import Candle, PaperTrade
from .results import BacktestResult
from .simulator import PaperBroker
from .strategy import StrategyConfig, analyze

# Exit rule names recorded on each closed trade.
OPPOSITE_SIGNAL = "opposite_signal"
MAX_HOLDING = "max_holding"
STOP_LOSS = "stop_loss"
TAKE_PROFIT = "take_profit"
END_OF_DATA = "end_of_data"


def _side_allowed(side: str, config: StrategyConfig) -> bool:
    """Entry-side gate. ``allowed_sides=None`` allows both directions."""

    if config.allowed_sides is None:
        return True
    return side in config.allowed_sides


def _levels_breached(
    trade: PaperTrade,
    bar: Candle,
    config: StrategyConfig,
) -> tuple[bool, bool]:
    """Return (stop_hit, target_hit) for a bar that has already closed.

    Only the high/low/close of ``bar`` are inspected. The caller is
    responsible for guaranteeing that ``bar`` closed before the decision and
    that the fill happens on a later bar.
    """

    stop_hit = False
    target_hit = False

    if config.stop_loss_pct is not None:
        distance = config.stop_loss_pct
        if trade.side == "long":
            stop_hit = bar.low <= trade.entry_price * (1.0 - distance)
        else:
            stop_hit = bar.high >= trade.entry_price * (1.0 + distance)

    if config.take_profit_pct is not None:
        distance = config.take_profit_pct
        if trade.side == "long":
            target_hit = bar.high >= trade.entry_price * (1.0 + distance)
        else:
            target_hit = bar.low <= trade.entry_price * (1.0 - distance)

    return stop_hit, target_hit


def run_backtest(
    candles: Sequence[Candle],
    config: StrategyConfig = StrategyConfig(),
    starting_balance: float = 10_000.0,
    risk_fraction: float = 0.01,
    costs: TradingCosts | None = None,
    evaluation_start: int | None = None,
) -> BacktestResult:
    """Run a paper-only backtest using next-candle open execution.

    ``costs`` is optional and defaults to the standard paper-trading costs,
    which preserves the original V1 baseline exactly. Passing
    ``TradingCosts(0, 0)`` enables a zero-cost diagnostic run.

    Optional Phase 6 exit rules (``max_holding_bars``, ``stop_loss_pct``,
    ``take_profit_pct``) are all disabled by default, so the default exit
    behaviour is the original V1 rule: close when an opposite-side signal
    appears, and close any remaining position on the final candle.

    ``evaluation_start`` is an optional index into ``candles`` from which
    entries are permitted. It exists for out-of-sample validation: candles
    before that index still feed the indicators so that lookback windows are
    fully warmed up, but no position can be opened there, so they never
    contribute trades. The account therefore starts flat, with the full
    ``starting_balance``, at the evaluation boundary. ``None`` (the default)
    disables the gate and reproduces the original behaviour exactly.

    Execution model for the optional rules: detection uses only bars that
    have already closed, and the fill always happens at the open of the
    following bar. Intrabar fills are never assumed, so a stop or target that
    is touched intrabar is treated as a trigger, not as a guaranteed fill
    price. When a single bar breaches both the stop and the target the order
    is unknowable from hourly data, so the stop is assumed to have been hit
    first; because the fill price is the next bar's open either way, this
    ambiguity does not change P&L, only the recorded exit label.
    """

    minimum_history = max(
        config.lookback + 2,
        config.slow_period,
    )

    if len(candles) <= minimum_history:
        raise ValueError(
            "not enough candles for configured backtest"
        )

    if evaluation_start is not None and not (
        minimum_history <= evaluation_start < len(candles)
    ):
        raise ValueError(
            "evaluation_start must be at least the minimum history and "
            "strictly less than the number of candles"
        )

    broker = PaperBroker(starting_balance, costs=costs)

    entry_index: int | None = None
    exit_counts: dict[str, int] = {}

    for index in range(minimum_history, len(candles)):
        current = candles[index]

        # Generate the signal using only candles that have closed.
        signal = analyze(
            candles[:index],
            config,
        )

        # Simulate execution at the next candle's open.
        execution_signal = replace(
            signal,
            timestamp=current.timestamp,
            price=current.open,
        )

        if broker.open_trade is not None and entry_index is not None:
            trade = broker.open_trade
            bars_held = index - entry_index
            exit_reason: str | None = None

            # Optional rules are evaluated on the bar that just closed
            # (candles[index - 1]); the fill is this bar's open.
            if bars_held >= 1:
                closed_bar = candles[index - 1]

                if (
                    config.max_holding_bars is not None
                    and bars_held >= config.max_holding_bars
                ):
                    exit_reason = MAX_HOLDING
                elif config.stop_loss_pct is not None or config.take_profit_pct is not None:
                    stop_hit, target_hit = _levels_breached(
                        trade, closed_bar, config
                    )
                    # Conservative: assume the stop was reached first.
                    if stop_hit:
                        exit_reason = STOP_LOSS
                    elif target_hit:
                        exit_reason = TAKE_PROFIT

            # Baseline rule: an opposite-side signal closes the position.
            if exit_reason is None and (
                signal.side in {"long", "short"}
                and signal.side != trade.side
            ):
                exit_reason = OPPOSITE_SIGNAL

            if exit_reason is not None:
                trade = broker.close(
                    current.open,
                    current.timestamp,
                )
                trade.exit_reason = exit_reason
                trade.bars_held = bars_held
                exit_counts[exit_reason] = (
                    exit_counts.get(exit_reason, 0) + 1
                )
                entry_index = None

        if (
            broker.open_trade is None
            and signal.side in {"long", "short"}
            and _side_allowed(signal.side, config)
            and (evaluation_start is None or index >= evaluation_start)
        ):
            broker.open_from_signal(
                execution_signal,
                risk_fraction=risk_fraction,
            )
            entry_index = index

    # Close any remaining position at the final candle's close.
    if broker.open_trade is not None:
        last = candles[-1]
        trade = broker.close(last.close, last.timestamp)
        trade.exit_reason = END_OF_DATA
        trade.bars_held = len(candles) - 1 - (entry_index or 0)
        exit_counts[END_OF_DATA] = exit_counts.get(END_OF_DATA, 0) + 1

    return BacktestResult(
        trades=broker.journal,
        starting_balance=starting_balance,
        ending_balance=broker.cash,
        exit_counts=exit_counts,
    )
