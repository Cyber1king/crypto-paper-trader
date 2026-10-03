"""Phase 12 tests for the execution model.

Every expected number here is hand-calculated on purpose, using small round
prices so the arithmetic can be checked by eye. No test asserts anything
about profitability or performance.

The two supported models are:

``cost_deduction`` (default)
    Fills equal the raw chart price. ``costs`` holds fees plus slippage.
    This is the legacy Phase 5-11 model.

``fill_price``
    Spread and slippage are applied to the fill price. Position size comes
    from the real entry fill, fees are charged on filled notional, and
    ``costs`` holds fees only because spread/slippage already sit inside the
    recorded prices.

Hand calculation used throughout:

    entry fill = reference x (1 + rate)   when buying
    entry fill = reference x (1 - rate)   when selling
    quantity   = cash x risk_fraction / entry fill
    net_pnl    = pnl - costs
"""
from datetime import datetime, timedelta, timezone

import pytest

from crypto_paper_lab.backtest import (
    STOP_LOSS,
    _levels_breached,
    run_backtest,
)
from crypto_paper_lab.costs import (
    COST_DEDUCTION,
    FILL_PRICE,
    TradingCosts,
)
from crypto_paper_lab.models import Candle, PaperTrade, Signal
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.stats import (
    cost_breakdown,
    total_fees,
    total_friction,
    total_slippage,
    total_spread,
)
from crypto_paper_lab.strategy import StrategyConfig

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def signal(side: str = "long", price: float = 100.0) -> Signal:
    return Signal(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        side,
        "test",
        price,
        price * 0.9,
        price * 1.1,
        "up",
        True,
        False,
    )


def zero_costs(model: str = FILL_PRICE, spread: float = 0.0) -> TradingCosts:
    """No fee, no slippage, no spread: fills equal the reference price."""

    return TradingCosts(
        fee_rate=0.0,
        slippage_rate=0.0,
        spread_rate=spread,
        execution_model=model,
    )


def slip_only(
    rate: float = 0.001,
    spread: float = 0.0,
    model: str = FILL_PRICE,
) -> TradingCosts:
    """Slippage (and optional spread) with no fee, to isolate price impact."""

    return TradingCosts(
        fee_rate=0.0,
        slippage_rate=rate,
        spread_rate=spread,
        execution_model=model,
    )


def close_now() -> datetime:
    return datetime(2026, 1, 2, tzinfo=timezone.utc)


def run_trade(
    side: str,
    p_in: float,
    p_out: float,
    costs: TradingCosts,
    cash: float = 10_000.0,
    risk: float = 0.10,
):
    broker = PaperBroker(cash, costs=costs)
    broker.open_from_signal(signal(side, p_in), risk_fraction=risk)

    return broker, broker.close(p_out, close_now())


# ---------------------------------------------------------------------------
# configuration validation
# ---------------------------------------------------------------------------


def test_default_model_is_legacy_cost_deduction() -> None:
    assert TradingCosts().execution_model == COST_DEDUCTION
    assert TradingCosts().spread_rate == 0.0


def test_adverse_rate_combines_spread_and_slippage() -> None:
    costs = TradingCosts(
        fee_rate=0.0,
        slippage_rate=0.0005,
        spread_rate=0.0002,
        execution_model=FILL_PRICE,
    )
    assert costs.adverse_rate == pytest.approx(0.0007)


def test_negative_rates_are_rejected() -> None:
    with pytest.raises(ValueError, match="fee_rate"):
        TradingCosts(fee_rate=-0.1)

    with pytest.raises(ValueError, match="slippage_rate"):
        TradingCosts(slippage_rate=-0.1)

    with pytest.raises(ValueError, match="spread_rate"):
        TradingCosts(spread_rate=-0.1, execution_model=FILL_PRICE)


def test_unknown_execution_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution_model"):
        TradingCosts(execution_model="leverage")  # type: ignore[arg-type]


def test_spread_requires_fill_price_model() -> None:
    """A spread cannot be separated from slippage under cost deduction."""

    with pytest.raises(ValueError, match="double count"):
        TradingCosts(spread_rate=0.0002)


def test_zero_spread_is_allowed_under_cost_deduction() -> None:
    assert TradingCosts(spread_rate=0.0).spread_rate == 0.0


# ---------------------------------------------------------------------------
# legacy model must not move
# ---------------------------------------------------------------------------


def test_cost_deduction_still_records_raw_prices() -> None:
    costs = TradingCosts(fee_rate=0.001, slippage_rate=0.0005)
    _, trade = run_trade("long", 100.0, 110.0, costs)

    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(110.0)
    assert trade.raw_entry_price == pytest.approx(100.0)
    assert trade.raw_exit_price == pytest.approx(110.0)


def test_cost_deduction_matches_pre_phase12_arithmetic() -> None:
    """Hand calculation: qty 10, fees 2.10, slippage 1.05, costs 3.15."""

    costs = TradingCosts(fee_rate=0.001, slippage_rate=0.0005)
    _, trade = run_trade("long", 100.0, 110.0, costs)

    assert trade.quantity == pytest.approx(10.0)
    assert trade.pnl == pytest.approx(100.0)
    assert trade.fee_total == pytest.approx(2.10)
    assert trade.slippage_total == pytest.approx(1.05)
    assert trade.spread_total == 0.0
    assert trade.costs == pytest.approx(3.15)
    assert trade.net_pnl == pytest.approx(96.85)
    assert trade.total_friction == pytest.approx(3.15)


# ---------------------------------------------------------------------------
# fill-price model: entry and exit prices
# ---------------------------------------------------------------------------


def test_fill_price_long_entry_buys_above_reference() -> None:
    """100 x 1.001 = 100.10; qty = 1000 / 100.10."""

    costs = slip_only(0.001)
    _, trade = run_trade("long", 100.0, 110.0, costs)

    assert trade.raw_entry_price == pytest.approx(100.0)
    assert trade.entry_price == pytest.approx(100.10)
    assert trade.quantity == pytest.approx(1000.0 / 100.10)


def test_fill_price_long_exit_sells_below_reference() -> None:
    """110 x 0.999 = 109.89."""

    costs = slip_only(0.001)
    _, trade = run_trade("long", 100.0, 110.0, costs)

    assert trade.raw_exit_price == pytest.approx(110.0)
    assert trade.exit_price == pytest.approx(109.89)


def test_fill_price_short_entry_sells_below_reference() -> None:
    """100 x 0.999 = 99.90; qty = 1000 / 99.90."""

    costs = slip_only(0.001)
    _, trade = run_trade("short", 100.0, 90.0, costs)

    assert trade.raw_entry_price == pytest.approx(100.0)
    assert trade.entry_price == pytest.approx(99.90)
    assert trade.quantity == pytest.approx(1000.0 / 99.90)


def test_fill_price_short_exit_buys_above_reference() -> None:
    """90 x 1.001 = 90.09."""

    costs = slip_only(0.001)
    _, trade = run_trade("short", 100.0, 90.0, costs)

    assert trade.raw_exit_price == pytest.approx(90.0)
    assert trade.exit_price == pytest.approx(90.09)


def test_fill_price_applies_slippage_on_both_legs() -> None:
    """Both legs move 0.001 against the trade, in either direction."""

    costs = slip_only(0.001)

    for side, p_out, expect_entry, expect_exit in (
        ("long", 110.0, 100.10, 109.89),
        ("short", 90.0, 99.90, 90.09),
    ):
        _, trade = run_trade(side, 100.0, p_out, costs)
        assert trade.entry_price == pytest.approx(expect_entry)
        assert trade.exit_price == pytest.approx(expect_exit)


def test_fill_price_long_profit_is_reduced_by_both_legs() -> None:
    """Hand calculation, qty = 1000/100.10:

    entry 100.10, exit 109.89 -> (109.89 - 100.10) x qty = 97.90...
    """

    costs = slip_only(0.001)
    _, trade = run_trade("long", 100.0, 110.0, costs)

    qty = 1000.0 / 100.10
    expected = (109.89 - 100.10) * qty

    assert trade.pnl == pytest.approx(expected)
    assert trade.pnl < 100.0  # never better than the frictionless 100.0


def test_fill_price_short_profit_is_reduced_by_both_legs() -> None:
    costs = slip_only(0.001)
    _, trade = run_trade("short", 100.0, 90.0, costs)

    qty = 1000.0 / 99.90
    expected = (99.90 - 90.09) * qty

    assert trade.pnl == pytest.approx(expected)
    assert trade.pnl < 100.0


def test_flat_trade_loses_slippage_in_both_directions() -> None:
    """Entering and leaving at the same reference price is not free.

    Round-trip slippage is 2 x 100 x 0.001 = 0.20 per unit, applied against
    the trade on both legs. Long: buy 100.10, sell 99.90, qty 1000/100.10.
    Short: sell 99.90, buy 100.10, qty 1000/99.90.
    """

    long_trade = run_trade("long", 100.0, 100.0, slip_only(0.001))[1]
    short_trade = run_trade("short", 100.0, 100.0, slip_only(0.001))[1]

    assert long_trade.entry_price == pytest.approx(100.10)
    assert long_trade.exit_price == pytest.approx(99.90)
    assert long_trade.pnl == pytest.approx(
        -0.20 * (1000.0 / 100.10), abs=1e-9
    )

    assert short_trade.entry_price == pytest.approx(99.90)
    assert short_trade.exit_price == pytest.approx(100.10)
    assert short_trade.pnl == pytest.approx(
        -0.20 * (1000.0 / 99.90), abs=1e-9
    )


# ---------------------------------------------------------------------------
# spread, separate from slippage
# ---------------------------------------------------------------------------


def test_spread_widens_the_fill_beyond_slippage_alone() -> None:
    """0.0002 spread on top of 0.0005 slippage -> 100 x 1.0007."""

    costs = TradingCosts(
        fee_rate=0.0,
        slippage_rate=0.0005,
        spread_rate=0.0002,
        execution_model=FILL_PRICE,
    )
    _, trade = run_trade("long", 100.0, 110.0, costs)

    assert trade.entry_price == pytest.approx(100.07)
    assert trade.exit_price == pytest.approx(109.923)


def test_spread_and_slippage_are_reported_separately() -> None:
    """Attribution uses the raw reference notional, 100 + 110, times qty."""

    costs = TradingCosts(
        fee_rate=0.0,
        slippage_rate=0.0005,
        spread_rate=0.0002,
        execution_model=FILL_PRICE,
    )
    _, trade = run_trade("long", 100.0, 110.0, costs)

    raw_notional = (100.0 + 110.0) * trade.quantity

    assert trade.spread_total == pytest.approx(raw_notional * 0.0002)
    assert trade.slippage_total == pytest.approx(raw_notional * 0.0005)
    assert trade.total_friction == pytest.approx(raw_notional * 0.0007)


def test_spread_is_not_charged_twice() -> None:
    """Friction must equal the single combined adverse move, once."""

    costs = TradingCosts(
        fee_rate=0.0,
        slippage_rate=0.0005,
        spread_rate=0.0002,
        execution_model=FILL_PRICE,
    )
    _, trade = run_trade("long", 100.0, 110.0, costs)

    # Total friction against the raw reference, counted once.
    qty = trade.quantity
    raw_move = (110.0 - 100.0) * qty
    assert raw_move - trade.pnl == pytest.approx(trade.total_friction)


# ---------------------------------------------------------------------------
# fees
# ---------------------------------------------------------------------------


def test_fill_price_fees_are_charged_on_filled_notional() -> None:
    """Fees use the filled notional (100.05 + 109.945) x qty x 0.001."""

    costs = TradingCosts(
        fee_rate=0.001,
        slippage_rate=0.0005,
        execution_model=FILL_PRICE,
    )
    _, trade = run_trade("long", 100.0, 110.0, costs)

    entry_fill = 100.0 * 1.0005     # 100.05
    exit_fill = 110.0 * 0.9995      # 109.945
    qty = 1000.0 / entry_fill
    expected_fee = (entry_fill + exit_fill) * qty * 0.001

    assert trade.entry_price == pytest.approx(entry_fill)
    assert trade.exit_price == pytest.approx(exit_fill)
    assert trade.fee_total == pytest.approx(expected_fee)
    assert trade.costs == pytest.approx(expected_fee)

    # Fees follow the notional actually transacted, not the raw reference.
    # Here 100.05 + 109.945 = 209.995 is just under the raw 210.0, because
    # adverse entry slippage is partly offset on the exit leg. The fee
    # therefore differs slightly from a raw-notional calculation.
    raw_fee = (100.0 * qty + 110.0 * qty) * 0.001
    assert trade.fee_total != pytest.approx(raw_fee, abs=1e-9)


def test_fee_is_charged_once_per_leg() -> None:
    """A 0.001 fee on a round trip costs 0.002 of notional in total."""

    costs = TradingCosts(
        fee_rate=0.001,
        slippage_rate=0.0,
        execution_model=FILL_PRICE,
    )
    _, trade = run_trade("long", 100.0, 100.0, costs)

    assert trade.fee_total == pytest.approx(2 * 100.0 * trade.quantity * 0.001)


def test_zero_costs_leave_pnl_untouched() -> None:
    for model in (COST_DEDUCTION, FILL_PRICE):
        _, trade = run_trade("long", 100.0, 110.0, zero_costs(model))
        assert trade.costs == 0.0
        assert trade.net_pnl == pytest.approx(trade.pnl)


def test_zero_costs_make_fills_equal_the_reference() -> None:
    _, trade = run_trade("long", 100.0, 110.0, zero_costs())

    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(110.0)
    assert trade.quantity == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# net P&L and balance consistency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("p_out", [50.0, 90.0, 100.0, 110.0, 150.0])
@pytest.mark.parametrize(
    "model", [COST_DEDUCTION, FILL_PRICE]
)
def test_net_pnl_equals_gross_minus_costs(
    side: str, p_out: float, model: str
) -> None:
    costs = TradingCosts(
        fee_rate=0.001,
        slippage_rate=0.0005,
        execution_model=model,
    )
    _, trade = run_trade(side, 100.0, p_out, costs)

    assert trade.net_pnl == pytest.approx(trade.pnl - trade.costs)


@pytest.mark.parametrize("side", ["long", "short"])
def test_balance_equals_starting_plus_summed_net_pnl(side: str) -> None:
    costs = TradingCosts(
        fee_rate=0.001,
        slippage_rate=0.0005,
        execution_model=FILL_PRICE,
    )
    broker = PaperBroker(10_000.0, costs=costs)

    broker.open_from_signal(signal(side, 100.0), risk_fraction=0.10)
    broker.close(105.0, close_now())
    first = broker.cash

    broker.open_from_signal(signal(side, 100.0), risk_fraction=0.10)
    broker.close(95.0, close_now())

    assert first == pytest.approx(
        10_000.0 + sum(t.net_pnl for t in broker.journal[:1])
    )
    assert broker.cash == pytest.approx(
        10_000.0 + sum(t.net_pnl for t in broker.journal)
    )


def test_position_size_uses_the_real_entry_fill() -> None:
    """Committed notional equals cash x risk_fraction in fill mode."""

    costs = zero_costs()
    _, trade = run_trade("long", 100.0, 110.0, costs, cash=10_000.0, risk=0.10)

    assert trade.entry_price * trade.quantity == pytest.approx(1000.0)


def test_legacy_position_size_uses_the_raw_price() -> None:
    costs = zero_costs(COST_DEDUCTION)
    _, trade = run_trade("long", 100.0, 110.0, costs, cash=10_000.0, risk=0.10)

    assert trade.entry_price * trade.quantity == pytest.approx(1000.0)
    assert trade.raw_entry_price == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# equivalence and monotonicity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("p_out", [90.0, 100.0, 110.0])
def test_models_agree_on_pnl_within_fee_base(side: str, p_out: float) -> None:
    """The models agree to within a fraction of a percent.

    They are not identical by construction. ``fill_price`` sizes each
    position from the slipped entry fill rather than the raw reference, so
    it holds marginally fewer units and pays fees on a marginally larger
    notional. Both differences are second-order in the rates and vanish as
    they approach zero. The 0.1% bound below is far wider than the effect
    for a 0.05% slippage rate.
    """

    legacy = run_trade(
        side,
        100.0,
        p_out,
        TradingCosts(fee_rate=0.001, slippage_rate=0.0005),
    )[1]
    filled = run_trade(
        side,
        100.0,
        p_out,
        TradingCosts(
            fee_rate=0.001,
            slippage_rate=0.0005,
            execution_model=FILL_PRICE,
        ),
    )[1]

    assert filled.net_pnl == pytest.approx(legacy.net_pnl, rel=1e-3)


def test_higher_costs_never_improve_net_pnl() -> None:
    """Monotonicity: adding friction cannot help."""

    results = []
    for slippage in (0.0, 0.0005, 0.002):
        costs = TradingCosts(
            fee_rate=0.001,
            slippage_rate=slippage,
            execution_model=FILL_PRICE,
        )
        results.append(run_trade("long", 100.0, 110.0, costs)[1].net_pnl)

    assert results[0] > results[1] > results[2]


def test_spread_reduces_net_pnl_monotonically() -> None:
    results = []
    for spread in (0.0, 0.0002, 0.001):
        costs = TradingCosts(
            fee_rate=0.0,
            slippage_rate=0.0005,
            spread_rate=spread,
            execution_model=FILL_PRICE,
        )
        results.append(run_trade("long", 100.0, 110.0, costs)[1].net_pnl)

    assert results[0] > results[1] > results[2]


# ---------------------------------------------------------------------------
# backtest / broker consistency
# ---------------------------------------------------------------------------


def _synthetic_candles(count: int = 60) -> list[Candle]:
    """Deterministic candles with a clear uptrend.

    Built by formula rather than randomness so every run is reproducible.
    """

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []

    for i in range(count):
        price = 100.0 + i * 0.5
        candles.append(
            Candle(
                timestamp=base.replace(hour=i % 24),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price + 0.5,
                volume=10.0,
            )
        )

    return candles


def test_backtest_and_broker_share_one_execution_model() -> None:
    """A backtest under fill_price must record real fills, not raw opens."""

    candles = _synthetic_candles()
    costs = TradingCosts(
        fee_rate=0.001,
        slippage_rate=0.0005,
        execution_model=FILL_PRICE,
    )
    result = run_backtest(candles, costs=costs)

    assert result.trades, "expected at least one trade on a trending series"

    for trade in result.trades:
        assert trade.entry_price != pytest.approx(trade.raw_entry_price)
        assert trade.exit_price != pytest.approx(trade.raw_exit_price)
        assert trade.net_pnl == pytest.approx(trade.pnl - trade.costs)


def test_backtest_under_legacy_model_still_records_raw_fills() -> None:
    candles = _synthetic_candles()
    costs = TradingCosts(fee_rate=0.001, slippage_rate=0.0005)
    result = run_backtest(candles, costs=costs)

    assert result.trades

    for trade in result.trades:
        assert trade.entry_price == pytest.approx(trade.raw_entry_price)
        assert trade.exit_price == pytest.approx(trade.raw_exit_price)


def test_stop_loss_is_anchored_to_the_real_entry_fill() -> None:
    """The Phase 12 fix: a stop must reference the price actually paid."""

    from crypto_paper_lab.strategy import StrategyConfig

    candles = _synthetic_candles()
    costs = TradingCosts(
        fee_rate=0.0,
        slippage_rate=0.002,
        execution_model=FILL_PRICE,
    )
    result = run_backtest(
        candles,
        StrategyConfig(stop_loss_pct=0.01),
        costs=costs,
    )

    assert result.trades

    for trade in result.trades:
        # entry_price is the fill, and the raw chart open differs from it.
        assert trade.entry_price > trade.raw_entry_price
        # The stop level is defined against the fill, not the raw open.
        stop_level = trade.entry_price * 0.99
        raw_level = trade.raw_entry_price * 0.99
        assert stop_level > raw_level


def test_backtest_is_deterministic() -> None:
    candles = _synthetic_candles()
    costs = TradingCosts(
        fee_rate=0.001,
        slippage_rate=0.0005,
        spread_rate=0.0002,
        execution_model=FILL_PRICE,
    )

    first = run_backtest(candles, costs=costs)
    second = run_backtest(candles, costs=costs)

    assert first.ending_balance == pytest.approx(second.ending_balance)
    assert first.total_trades == second.total_trades
    assert [t.net_pnl for t in first.trades] == pytest.approx(
        [t.net_pnl for t in second.trades]
    )


def test_no_leverage_or_margin_is_introduced() -> None:
    """Position size stays bounded by the configured risk fraction."""

    costs = zero_costs()

    for side in ("long", "short"):
        _, trade = run_trade(side, 100.0, 110.0, costs, risk=1.0)
        assert trade.quantity * trade.entry_price == pytest.approx(10_000.0)

    broker = PaperBroker(10_000.0, costs=costs)
    with pytest.raises(ValueError, match="risk_fraction"):
        broker.open_from_signal(signal("long"), risk_fraction=0.0)

    with pytest.raises(ValueError, match="risk_fraction"):
        broker.open_from_signal(signal("long"), risk_fraction=1.5)# ---------------------------------------------------------------------------
# Finding 1 - discriminating stop-anchor tests
#
# The window between a raw-referenced stop and a fill-referenced stop is
#   raw_stop  = P * (1 - d)
#   fill_stop = P * (1 + s) * (1 - d)
# so the gap is P * (1 - d) * s. Any candle low inside that gap triggers the
# stop under fill_price and must NOT trigger it under cost_deduction.
# ---------------------------------------------------------------------------

ANCHOR_SLIP = 0.005
ANCHOR_STOP = 0.01
ANCHOR_REF = 121.5


def _anchor_levels() -> tuple[float, float, float]:
    """Return (raw_stop, fill_stop, discriminating_low) from the formulas."""

    raw_stop = ANCHOR_REF * (1 - ANCHOR_STOP)
    fill = ANCHOR_REF * (1 + ANCHOR_SLIP)
    fill_stop = fill * (1 - ANCHOR_STOP)
    low = (raw_stop + fill_stop) / 2

    return raw_stop, fill_stop, low


def test_anchor_window_is_ordered_as_expected() -> None:
    raw_stop, fill_stop, low = _anchor_levels()

    assert raw_stop < low < fill_stop


def test_stop_anchor_discriminates_between_execution_models() -> None:
    """The same candle low must stop out under fill_price only.

    Under fill_price the recorded entry price is the fill, so the stop is
    measured from 121.5 x 1.005 = 122.1075 and sits at 120.886425. Under
    cost_deduction the recorded entry price is the raw reference 121.5, so
    the stop sits at 120.285. A low of 120.5857125 is between the two.
    """

    raw_stop, fill_stop, low = _anchor_levels()
    bar = Candle(
        datetime(2026, 1, 3, tzinfo=timezone.utc),
        open=ANCHOR_REF,
        high=ANCHOR_REF + 1.0,
        low=low,
        close=ANCHOR_REF,
        volume=10.0,
    )
    config = StrategyConfig(stop_loss_pct=ANCHOR_STOP)

    legacy_trade = PaperTrade(
        side="long",
        entry_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        entry_price=ANCHOR_REF,
        quantity=10.0,
    )
    filled_trade = PaperTrade(
        side="long",
        entry_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        entry_price=ANCHOR_REF * (1 + ANCHOR_SLIP),
        quantity=10.0,
    )

    assert legacy_trade.entry_price * (1 - ANCHOR_STOP) == pytest.approx(
        raw_stop
    )
    assert filled_trade.entry_price * (1 - ANCHOR_STOP) == pytest.approx(
        fill_stop
    )

    legacy_stop, _ = _levels_breached(legacy_trade, bar, config)
    filled_stop, _ = _levels_breached(filled_trade, bar, config)

    assert legacy_stop is False, "raw-referenced stop must NOT be hit"
    assert filled_stop is True, "fill-referenced stop MUST be hit"


def _anchor_series() -> list[Candle]:
    """Series whose single dip falls inside the anchor window.

    After the dip prices climb steadily, so the raw-referenced stop is never
    reached and only the fill-referenced stop can fire.
    """

    raw_stop, _, low = _anchor_levels()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[tuple[float, float, float, float]] = []

    for i in range(20):
        v = 100.0 + i
        rows.append((v - 0.5, v + 1.0, v - 1.0, v))

    rows.append((119.5, 124.0, 119.0, 123.0))
    rows.append((123.0, 124.0, 121.0, 121.5))
    rows.append((ANCHOR_REF, ANCHOR_REF + 1.0, low, low + 0.3))

    price = ANCHOR_REF
    for _ in range(23, 34):
        price += 0.8
        rows.append((price - 0.4, price + 0.4, price - 0.8, price))

    candles = [
        Candle(
            timestamp=start + timedelta(hours=i),
            open=o,
            high=h,
            low=l,
            close=c,
            volume=10.0,
        )
        for i, (o, h, l, c) in enumerate(rows)
    ]

    # Guard the construction itself.
    assert candles[22].low == pytest.approx(low)
    assert raw_stop < min(c.low for c in candles[23:])

    return candles


def test_stop_loss_exit_counts_differ_between_execution_models() -> None:
    """Only fill_price should ever stop out on this series."""

    candles = _anchor_series()
    config = StrategyConfig(stop_loss_pct=ANCHOR_STOP)

    legacy = run_backtest(
        candles,
        config,
        costs=TradingCosts(0.0, ANCHOR_SLIP, 0.0, COST_DEDUCTION),
    )
    filled = run_backtest(
        candles,
        config,
        costs=TradingCosts(0.0, ANCHOR_SLIP, 0.0, FILL_PRICE),
    )

    legacy_stops = legacy.exit_counts.get(STOP_LOSS, 0)
    filled_stops = filled.exit_counts.get(STOP_LOSS, 0)

    assert legacy_stops == 0, "cost_deduction must not stop out"
    assert filled_stops == 1, "fill_price must stop out exactly once"
    assert filled_stops != legacy_stops

    stopped = [t for t in filled.trades if t.exit_reason == STOP_LOSS]
    assert len(stopped) == 1
    # It stops on the first bar after entry, because that bar's low is
    # already past the fill-referenced stop.
    assert stopped[0].bars_held == 1
    assert stopped[0].entry_price == pytest.approx(
        ANCHOR_REF * (1 + ANCHOR_SLIP)
    )


def test_fill_referenced_stop_fires_earlier_than_raw_referenced() -> None:
    """Same shape, but the raw stop fires later rather than never."""

    raw_stop, _, low = _anchor_levels()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[tuple[float, float, float, float]] = []

    for i in range(20):
        v = 100.0 + i
        rows.append((v - 0.5, v + 1.0, v - 1.0, v))

    rows.append((119.5, 124.0, 119.0, 123.0))
    rows.append((123.0, 124.0, 121.0, 121.5))
    rows.append((ANCHOR_REF, ANCHOR_REF + 1.0, low, ANCHOR_REF))
    price = ANCHOR_REF
    for _ in range(23, 28):
        price -= 3.0
        rows.append((price, price + 0.5, price - 1.0, price - 0.5))

    candles = [
        Candle(
            start + timedelta(hours=i), o, h, l, c, 10.0
        )
        for i, (o, h, l, c) in enumerate(rows)
    ]
    config = StrategyConfig(stop_loss_pct=ANCHOR_STOP)

    legacy = run_backtest(
        candles,
        config,
        costs=TradingCosts(0.0, ANCHOR_SLIP, 0.0, COST_DEDUCTION),
    )
    filled = run_backtest(
        candles,
        config,
        costs=TradingCosts(0.0, ANCHOR_SLIP, 0.0, FILL_PRICE),
    )

    legacy_bars = next(
        t.bars_held for t in legacy.trades if t.exit_reason == STOP_LOSS
    )
    filled_bars = next(
        t.bars_held for t in filled.trades if t.exit_reason == STOP_LOSS
    )

    assert filled_bars < legacy_bars
    assert raw_stop == pytest.approx(ANCHOR_REF * 0.99)


# ---------------------------------------------------------------------------
# Finding 2 + 5 - cost reporting and the legacy cost identity
# ---------------------------------------------------------------------------



def _two_trade_run(costs: TradingCosts):
    broker = PaperBroker(10_000.0, costs=costs)
    broker.open_from_signal(signal("long", 100.0), risk_fraction=0.10)
    broker.close(110.0, close_now())
    broker.open_from_signal(signal("short", 100.0), risk_fraction=0.10)
    broker.close(92.0, close_now())

    return broker


def test_legacy_costs_equal_total_friction() -> None:
    """Finding 5: under cost_deduction the two metrics are the same number."""

    costs = TradingCosts(0.001, 0.0005, 0.0, COST_DEDUCTION)
    broker = _two_trade_run(costs)

    assert total_friction(broker.journal) == pytest.approx(
        sum(t.costs for t in broker.journal)
    )
    assert total_friction(broker.journal) == pytest.approx(
        sum(t.total_friction for t in broker.journal)
    )


def test_reported_total_friction_equals_sum_under_fill_price() -> None:
    """Finding 2: reporting must use total_friction under fill_price."""

    costs = TradingCosts(0.001, 0.0005, 0.0002, FILL_PRICE)
    broker = _two_trade_run(costs)

    naive = sum(t.costs for t in broker.journal)
    reported = total_friction(broker.journal)

    assert reported == pytest.approx(
        sum(t.total_friction for t in broker.journal)
    )
    # The naive metric is materially lower: this is the bug being fixed.
    assert reported > naive
    assert total_spread(broker.journal) > 0.0


def test_summing_costs_would_understate_fill_price_by_the_spread() -> None:
    """Quantify the reporting gap that Finding 2 identified."""

    costs = TradingCosts(0.001, 0.0005, 0.0002, FILL_PRICE)
    broker = _two_trade_run(costs)

    gap = total_friction(broker.journal) - sum(
        t.costs for t in broker.journal
    )

    assert gap == pytest.approx(
        total_slippage(broker.journal) + total_spread(broker.journal)
    )


def test_cost_breakdown_components_sum_to_total_friction() -> None:
    for model, spread in ((COST_DEDUCTION, 0.0), (FILL_PRICE, 0.0002)):
        costs = TradingCosts(0.001, 0.0005, spread, model)
        broker = _two_trade_run(costs)
        parts = cost_breakdown(broker.journal)

        assert parts["fee_total"] == pytest.approx(total_fees(broker.journal))
        assert parts["total_friction"] == pytest.approx(
            total_friction(broker.journal)
        )
        assert (
            parts["fee_total"]
            + parts["spread_total"]
            + parts["slippage_total"]
        ) == pytest.approx(parts["total_friction"])


def test_total_friction_ignores_open_trades() -> None:
    """Open trades have no friction yet and must not break the sum."""

    costs = TradingCosts(0.001, 0.0005, 0.0, FILL_PRICE)
    broker = PaperBroker(10_000.0, costs=costs)
    broker.open_from_signal(signal("long", 100.0), risk_fraction=0.10)

    assert total_friction([broker.open_trade]) == 0.0


def test_legacy_cost_formula_against_independent_values() -> None:
    """Finding 5 regression: recompute the legacy formula by hand.

    cash 10000, risk 0.10 at reference 100 -> quantity 10.
    Long 100 -> 110: notional 1000 + 1100 = 2100.
      fee      = 2100 * 0.001                        = 2.10
      slippage = 2100 * 0.0005                       = 1.05
      costs                                          = 3.15
      gross    = (110 - 100) * 10                    = 100.00
      net                                           = 96.85
    """

    costs = TradingCosts(0.001, 0.0005, 0.0, COST_DEDUCTION)
    broker = PaperBroker(10_000.0, costs=costs)
    broker.open_from_signal(signal("long", 100.0), risk_fraction=0.10)
    trade = broker.close(110.0, close_now())

    notional = 2100.0

    assert trade.quantity == pytest.approx(10.0)
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(110.0)
    assert trade.pnl == pytest.approx(100.0)
    assert trade.fee_total == pytest.approx(notional * 0.001)
    assert trade.slippage_total == pytest.approx(notional * 0.0005)
    assert trade.spread_total == 0.0
    assert trade.costs == pytest.approx(3.15)
    assert trade.net_pnl == pytest.approx(96.85)
    assert trade.total_friction == pytest.approx(3.15)
    assert trade.pnl - trade.costs == pytest.approx(trade.net_pnl)


def test_legacy_cost_formula_short_side_independent_values() -> None:
    """Short 100 -> 90: notional 1000 + 900 = 1900, gross (100-90)*10."""

    costs = TradingCosts(0.001, 0.0005, 0.0, COST_DEDUCTION)
    broker = PaperBroker(10_000.0, costs=costs)
    broker.open_from_signal(signal("short", 100.0), risk_fraction=0.10)
    trade = broker.close(90.0, close_now())

    notional = 1900.0

    assert trade.pnl == pytest.approx(100.0)
    assert trade.fee_total == pytest.approx(notional * 0.001)
    assert trade.slippage_total == pytest.approx(notional * 0.0005)
    assert trade.costs == pytest.approx(2.85)
    assert trade.net_pnl == pytest.approx(97.15)
    assert trade.total_friction == pytest.approx(2.85)


# ---------------------------------------------------------------------------
# Finding 4 - raw_entry_price invariant
# ---------------------------------------------------------------------------


def test_missing_raw_entry_price_raises_under_fill_price() -> None:
    """Friction attribution must fail loudly, not silently under-report."""

    costs = TradingCosts(0.001, 0.0005, 0.0002, FILL_PRICE)
    broker = PaperBroker(10_000.0, costs=costs)
    broker.open_trade = PaperTrade(
        side="long",
        entry_time=close_now(),
        entry_price=100.0,
        quantity=10.0,
    )

    with pytest.raises(ValueError, match="raw_entry_price"):
        broker.close(110.0, close_now())


def test_missing_raw_entry_price_is_allowed_under_cost_deduction() -> None:
    """Legacy trades built without the field must keep working."""

    costs = TradingCosts(0.001, 0.0005, 0.0, COST_DEDUCTION)
    broker = PaperBroker(10_000.0, costs=costs)
    broker.open_trade = PaperTrade(
        side="long",
        entry_time=close_now(),
        entry_price=100.0,
        quantity=10.0,
    )
    trade = broker.close(110.0, close_now())

    assert trade.costs == pytest.approx(3.15)
    assert trade.total_friction == pytest.approx(3.15)


def test_open_from_signal_always_sets_the_raw_reference() -> None:
    """The normal path satisfies the invariant for both models."""

    for model in (COST_DEDUCTION, FILL_PRICE):
        costs = TradingCosts(0.001, 0.0005, 0.0, model)
        broker = PaperBroker(10_000.0, costs=costs)
        trade = broker.open_from_signal(
            signal("long", 100.0), risk_fraction=0.10
        )

        assert trade.raw_entry_price == pytest.approx(100.0)

        closed = broker.close(110.0, close_now())
        assert closed.raw_exit_price == pytest.approx(110.0)
        assert closed.total_friction is not None
        assert closed.total_friction > 0.0# ---------------------------------------------------------------------------
# Finding 1 (cont.) - the take-profit branch and the short side
#
# For a long the fill is ABOVE the reference, so the fill-referenced
# take-profit sits ABOVE the raw-referenced one and is harder to reach. For a
# short the fill is BELOW the reference, so the fill-referenced stop sits
# BELOW the raw-referenced one and is easier to reach. Both directions of the
# ``(1 + distance)`` branch are pinned here.
# ---------------------------------------------------------------------------

TP_RATE = 0.01
TP_SLIP = 0.005
TP_REF = 121.5


def test_stop_anchor_discriminates_for_short() -> None:
    """A short's fill is below the reference, so its stop is easier to hit.

    raw stop  = 121.5 * (1 + 0.01)                = 122.715
    fill stop = 121.5 * 0.995 * (1 + 0.01)         = 120.8925
    A high of 121.80375 lies between them, so only the fill-referenced stop
    fires. This pins the ``(1 + distance)`` branch for shorts.
    """

    raw_stop = TP_REF * (1 + TP_RATE)
    fill = TP_REF * (1 - TP_SLIP)
    fill_stop = fill * (1 + TP_RATE)
    high = (raw_stop + fill_stop) / 2

    assert fill_stop < high < raw_stop

    bar = Candle(
        datetime(2026, 1, 3, tzinfo=timezone.utc),
        open=TP_REF,
        high=high,
        low=TP_REF - 1.0,
        close=TP_REF,
        volume=10.0,
    )
    config = StrategyConfig(stop_loss_pct=TP_RATE)

    legacy = PaperTrade(
        side="short",
        entry_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        entry_price=TP_REF,
        quantity=10.0,
    )
    filled = PaperTrade(
        side="short",
        entry_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        entry_price=fill,
        quantity=10.0,
    )

    legacy_stop, _ = _levels_breached(legacy, bar, config)
    filled_stop, _ = _levels_breached(filled, bar, config)

    assert legacy_stop is False
    assert filled_stop is True


def test_take_profit_anchor_is_harder_to_reach_for_a_long() -> None:
    """A long's fill is above the reference, so its target is higher.

    raw target  = 121.5 * (1 + 0.01)               = 122.715
    fill target = 122.1075 * (1 + 0.01)             = 123.328575
    A high of 123.0217875 lies between them, so the raw-referenced target
    fires and the fill-referenced one does not.
    """

    raw_target = TP_REF * (1 + TP_RATE)
    fill = TP_REF * (1 + TP_SLIP)
    fill_target = fill * (1 + TP_RATE)
    high = (raw_target + fill_target) / 2

    assert raw_target < high < fill_target

    bar = Candle(
        datetime(2026, 1, 3, tzinfo=timezone.utc),
        open=TP_REF,
        high=high,
        low=TP_REF - 1.0,
        close=TP_REF,
        volume=10.0,
    )
    config = StrategyConfig(take_profit_pct=TP_RATE)

    legacy = PaperTrade(
        side="long",
        entry_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        entry_price=TP_REF,
        quantity=10.0,
    )
    filled = PaperTrade(
        side="long",
        entry_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        entry_price=fill,
        quantity=10.0,
    )

    _, legacy_target = _levels_breached(legacy, bar, config)
    _, filled_target = _levels_breached(filled, bar, config)

    assert legacy_target is True
    assert filled_target is False


def test_take_profit_anchor_discriminates_for_short() -> None:
    """A short's fill is below the reference, so its target sits lower.

    raw target  = 121.5 * (1 - 0.01)               = 120.285
    fill target = 120.8925 * (1 - 0.01)            = 119.683575

    Because the fill-referenced target is the lower of the two, a candle can
    only ever discriminate in one direction here: a low of 119.9842875 sits
    above the fill target but below the raw target, so the raw-referenced
    target fires and the fill-referenced one does not. There is no low that
    fires the fill target alone, since anything at or below it is also at or
    below the raw target.
    """

    raw_target = TP_REF * (1 - TP_RATE)
    fill = TP_REF * (1 - TP_SLIP)
    fill_target = fill * (1 - TP_RATE)
    low = (fill_target + raw_target) / 2

    assert fill_target < low < raw_target

    bar = Candle(
        datetime(2026, 1, 3, tzinfo=timezone.utc),
        open=TP_REF,
        high=TP_REF + 1.0,
        low=low,
        close=TP_REF,
        volume=10.0,
    )
    config = StrategyConfig(take_profit_pct=TP_RATE)

    legacy = PaperTrade(
        side="short",
        entry_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        entry_price=TP_REF,
        quantity=10.0,
    )
    filled = PaperTrade(
        side="short",
        entry_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        entry_price=fill,
        quantity=10.0,
    )

    _, legacy_target = _levels_breached(legacy, bar, config)
    _, filled_target = _levels_breached(filled, bar, config)

    assert legacy_target is True
    assert filled_target is False
