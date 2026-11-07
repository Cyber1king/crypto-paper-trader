"""Safe read-only LiveBroker view over the step-driven paper replay.

Paper execution is controlled by advancing the replay. This adapter exposes
its account and position state without pretending that replay steps are live
broker orders.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .base import (
    AccountSnapshot,
    BrokerError,
    LiveBroker,
    LiveTradingDisabled,
    OrderRejected,
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    Tick,
)


class PaperBrokerAdapter(LiveBroker):
    """Expose a ``ReplaySession``'s authoritative state through ``LiveBroker``."""

    def __init__(self, replay_session) -> None:
        self.replay_session = replay_session

    def broker_name(self) -> str:
        """Return the stable identifier for the paper replay broker."""
        return "paper"

    def get_balance(self) -> AccountSnapshot:
        """Return a live snapshot of the paper replay's balance and equity."""
        replay = self.replay_session.replay
        state = replay.state
        instrument = replay.config.asset
        currency = "USDT" if instrument.endswith("/USDT") else "USD"

        return AccountSnapshot(
            broker="paper",
            account_id=replay.replay_id or "paper-default",
            currency=currency,
            balance=state.balance,
            equity=state.balance,
            free_margin=state.balance,
            used_margin=0.0,
            leverage=None,
            timestamp=datetime.now(timezone.utc),
            stale_since=None,
        )

    def get_positions(self) -> list[Position]:
        """Return the replay's open position, if one currently exists."""
        replay = self.replay_session.replay
        state = replay.state
        if not state.has_open_position:
            return []

        trade = state.open_position
        return [
            Position(
                instrument=replay.config.asset,
                side=trade.side,
                quantity=trade.quantity,
                entry_price=trade.entry_price,
                entry_time=trade.entry_time,
                unrealized_pnl=None,
                broker_position_id=None,
            )
        ]

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Refuse orders because paper execution is driven by replay steps.

        The paper engine is driven by stepping the replay, not by accepting
        orders through this interface. This method exists to satisfy the
        contract, so that any code written against LiveBroker will not
        accidentally try to place paper orders through a live interface.
        """
        raise OrderRejected(
            "paper adapter does not accept orders; use /api/replay/step to "
            "advance the paper replay"
        )

    def cancel_order(self, client_order_id: str) -> bool:
        """Return False because paper replay has no pending orders.

        Paper engine has no pending orders; orders execute immediately when
        the replay steps.
        """
        return False

    def close_position(self, instrument: str) -> OrderResult | None:
        """Refuse direct closes; strategy exits occur as the replay advances."""
        raise OrderRejected(
            "paper adapter cannot close positions via this interface; use "
            "/api/replay/step to advance until the strategy exits"
        )
