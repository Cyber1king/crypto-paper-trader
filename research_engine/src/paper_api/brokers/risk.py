"""First-gate risk limits and an explicit, sticky kill switch.

All limits are evaluated against the pre-trade state. Passing these checks is
not a guarantee of execution: the broker may still reject an order, for example
because of insufficient margin. This module is a first gate, not a substitute
for broker-side checks.

``max_risk_per_trade_pct`` is recorded as a limit for strategy policy, but is
not directly enforced here. Position sizing against a stop loss belongs in the
strategy layer; this module does not invent a sizing algorithm.

Daily loss is measured using realized P&L only. Unrealized losses are not
counted in this first version. The kill switch is sticky: nothing in this
module resets it automatically; reset requires an explicit call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .base import OrderRequest, RiskLimitExceeded


@dataclass(frozen=True)
class RiskLimits:
    """Restrictive defaults for pre-trade risk checks.

    ``max_risk_per_trade_pct`` is documented for the strategy layer. It is not
    enforced here because calculating position size requires stop-loss data.
    """

    max_risk_per_trade_pct: float = 0.01
    max_open_positions: int = 3
    max_daily_loss_pct: float = 0.03
    max_total_exposure_pct: float = 0.50
    max_positions_per_instrument: int = 1
    max_order_notional_pct: float = 0.20


@dataclass
class RiskState:
    """Mutable account risk state used for pre-trade checks."""

    starting_equity_today: float
    current_equity: float
    realized_pnl_today: float = 0.0
    open_positions_count: int = 0
    positions_per_instrument: dict[str, int] = field(default_factory=dict)
    total_exposure: float = 0.0
    kill_switch_engaged: bool = False


KILL_SWITCH_LOG: list[tuple[datetime, str]] = []


def check_order(
    state: RiskState,
    limits: RiskLimits,
    request: OrderRequest,
    current_price: float,
    equity: float,
) -> None:
    """Raise ``RiskLimitExceeded`` when a pre-trade limit is breached.

    This is the first risk gate only; passing it does not replace broker-side
    validation such as margin checks. Daily loss uses realized P&L only, so
    unrealized losses are not included in this version.
    """
    if state.kill_switch_engaged:
        raise RiskLimitExceeded("kill_switch")

    if (
        state.positions_per_instrument.get(request.instrument, 0)
        >= limits.max_positions_per_instrument
    ):
        raise RiskLimitExceeded("max_positions_per_instrument")

    if state.open_positions_count >= limits.max_open_positions:
        raise RiskLimitExceeded("max_open_positions")

    order_notional = request.quantity * current_price
    if order_notional > equity * limits.max_order_notional_pct:
        raise RiskLimitExceeded("max_order_notional")

    if (
        state.realized_pnl_today
        <= -state.starting_equity_today * limits.max_daily_loss_pct
    ):
        raise RiskLimitExceeded("max_daily_loss")

    if (
        state.total_exposure + order_notional
        > equity * limits.max_total_exposure_pct
    ):
        raise RiskLimitExceeded("max_total_exposure")


def engage_kill_switch(state: RiskState, reason: str) -> None:
    """Engage the sticky kill switch and append a UTC timestamped log entry.

    The switch stays engaged until ``reset_kill_switch`` is called explicitly.
    """
    state.kill_switch_engaged = True
    KILL_SWITCH_LOG.append((datetime.now(timezone.utc), reason))


def reset_kill_switch(state: RiskState) -> None:
    """Explicitly reset the sticky kill switch; it is never reset automatically."""
    state.kill_switch_engaged = False
