"""In-memory paper session for the local API.

This is the smallest wrapper that lets the API expose authoritative engine
state. It owns exactly one :class:`~crypto_paper_lab.simulator.PaperBroker`
and **reads** it. It performs no arithmetic of its own: every number in
:class:`SessionView` is copied straight from the engine, and the realized P&L
is the one subtraction ``balance - starting_balance`` that the engine itself
performs in :class:`~crypto_paper_lab.results.BacktestResult`.

Phase 16B scope, deliberately narrow:

* **No** market-data ingestion, so there is no current candle and no signal.
* **No** trade execution, so ``open_trade`` is always ``None`` and the journal
  is always empty.
* **No** replay, so the session has no position within a candle series.
* **No** persistence.

Consequently several fields proposed in the integration plan's
``SessionSnapshot`` are *not* derivable yet and are therefore absent rather
than faked - see :data:`UNSUPPORTED_FIELDS`.

The authoritative starting balance is ``walkforward.STARTING_BALANCE``
(10,000.0), which is also ``PaperBroker``'s own default. The dashboard mock's
100,000 is a frontend fiction and is deliberately not used.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from crypto_paper_lab.costs import TradingCosts
from crypto_paper_lab.simulator import PaperBroker
from crypto_paper_lab.strategy import StrategyConfig
from crypto_paper_lab.walkforward import (
    RISK_FRACTION,
    STARTING_BALANCE,
    baseline_config,
    config_hash,
    costs_hash,
    phase13_costs,
)

#: Identifies the session as simulated. There is no other mode, and no
#: credential, venue or wallet concept exists anywhere in this package.
MODE_PAPER = "paper"

#: No replay engine exists in Phase 16B, so a freshly constructed session is
#: idle: it holds state and reports it, but advances nothing.
STATE_IDLE = "idle"


#: Fields from the integration plan's SessionSnapshot that this phase cannot
#: honestly produce, with the reason. Recorded here so the omission is
#: documented in code rather than looking like an oversight.
UNSUPPORTED_FIELDS: dict[str, str] = {
    "replay_index": "no replay engine in Phase 16B",
    "current_candle": "no market-data ingestion in Phase 16B",
    "last_signal": "requires candles; no ingestion in Phase 16B",
    "bars_processed": "follows replay; not applicable",
    "dataset_id": "no dataset is loaded in Phase 16B",
    "total_candles": "no dataset is loaded in Phase 16B",
    "unrealized_pnl": "requires an open position and a mark price; "
                      "no execution and no ingestion in Phase 16B",
    "equity": "balance plus unrealized_pnl, which is unavailable",
    "available_balance": "defined as equity; equity is unavailable",
    "reserved_capital": "the engine has no margin concept, so there is no "
                        "authoritative value to report",
    "statistics": "degenerate with zero trades; belongs to /api/statistics",
}


@dataclass(frozen=True)
class StrategyIdentity:
    """Identity of the strategy configuration driving the session."""

    config_repr: str
    config_hash: str


@dataclass(frozen=True)
class ExecutionIdentity:
    """Identity of the execution-cost model driving the session."""

    execution_model: str
    fee_rate: float
    slippage_rate: float
    spread_rate: float
    costs_repr: str
    costs_hash: str
    risk_fraction: float


@dataclass(frozen=True)
class AccountState:
    """Account figures, each copied from the broker without recomputation."""

    starting_balance: float
    balance: float
    realized_pnl: float
    trade_count: int


@dataclass(frozen=True)
class PositionState:
    """The open position, limited to fields the engine populates at entry.

    Deliberately absent, because ``PaperBroker.open_from_signal`` does not
    compute them and their dataclass defaults would be reported as if they
    were real:

    * ``costs``, ``fee_total``, ``slippage_total``, ``spread_total`` - all
      ``0.0`` until ``close()`` runs. Exposing ``0.0`` would claim an open
      trade cost nothing.
    * ``bars_held`` - ``0`` until the caller records it; the broker does not
      track it.
    * ``exit_*`` - meaningless while open.

    There is also **no** mark price and **no** unrealized P&L. The engine has
    no live price feed, so any current value would be invented.
    """

    side: str
    entry_time: datetime
    entry_price: float
    quantity: float
    reason: str
    raw_entry_price: float | None
    signal_close: float | None
    trend_state: str | None
    breakout_distance: float | None
    retest_distance: float | None
    realised_volatility: float | None
    mean_range: float | None
    support_at_entry: float | None
    resistance_at_entry: float | None


@dataclass(frozen=True)
class SessionView:
    """A read-only projection of the session, safe to serialise."""

    service: str
    session_id: str
    mode: str
    state: str
    active: bool
    account: AccountState
    strategy: StrategyIdentity
    execution: ExecutionIdentity
    has_open_position: bool


class PaperSession:
    """An in-memory paper-trading session backed by one ``PaperBroker``.

    The broker remains the single source of truth for balances, positions and
    the trade journal. This class adds no accounting: it exposes what the
    broker already holds.
    """

    def __init__(
        self,
        service: str,
        starting_balance: float = STARTING_BALANCE,
        config: StrategyConfig | None = None,
        costs: TradingCosts | None = None,
        broker: PaperBroker | None = None,
    ) -> None:
        self._service = service
        # An injected broker is a testability seam for controlled fixtures.
        # It must be fully populated by the engine itself; nothing here
        # fabricates a trade. Routes never receive a broker to mutate.
        self._broker = broker if broker is not None else PaperBroker(
            starting_balance=starting_balance,
            costs=costs if costs is not None else phase13_costs(),
        )
        self._config = config if config is not None else baseline_config()
        self._costs = self._broker.costs
        self._session_id = str(uuid4())

    @property
    def session_id(self) -> str:
        """Identity of this session.

        Generated once per session and stable for its lifetime, so repeated
        reads are deterministic. It intentionally differs between processes;
        a session is an instance, not a configuration.
        """

        return self._session_id

    @property
    def broker(self) -> PaperBroker:
        """The authoritative broker. Exposed read-only for later phases."""

        return self._broker

    def use_broker(self, broker: PaperBroker) -> None:
        """Re-point this session at a different broker, keeping its identity.

        Added in Phase 17D. ``crypto_paper_lab.replay.Replay.reset()`` constructs a
        **new** ``PaperBroker`` rather than clearing the old one, so a session left
        bound to the previous broker would go on reporting the balance and journal
        it happened to hold at that moment. That is two sources of truth for the
        same simulated money, which is precisely what the architecture forbids.

        Rebinding in place keeps ``session_id`` stable, so ``/api/session`` stays
        deterministic while ``/api/account``, ``/api/trades`` and
        ``/api/statistics`` follow the replay's current broker.
        """

        self._broker = broker
        self._costs = broker.costs

    @property
    def config(self) -> StrategyConfig:
        return self._config

    @property
    def account(self) -> AccountState:
        """Account figures read from the broker. No arithmetic beyond the
        engine's own ``balance - starting_balance`` definition."""

        starting_balance = self._broker.starting_balance
        balance = self._broker.cash

        return AccountState(
            starting_balance=starting_balance,
            balance=balance,
            realized_pnl=balance - starting_balance,
            trade_count=len(self._broker.journal),
        )

    @property
    def position(self) -> PositionState | None:
        """The open position, or ``None``. Never a fabricated valuation."""

        trade = self._broker.open_trade

        if trade is None:
            return None

        return PositionState(
            side=trade.side,
            entry_time=trade.entry_time,
            entry_price=trade.entry_price,
            quantity=trade.quantity,
            reason=trade.reason,
            raw_entry_price=trade.raw_entry_price,
            signal_close=trade.signal_close,
            trend_state=trade.trend_state,
            breakout_distance=trade.breakout_distance,
            retest_distance=trade.retest_distance,
            realised_volatility=trade.realised_volatility,
            mean_range=trade.mean_range,
            support_at_entry=trade.support_at_entry,
            resistance_at_entry=trade.resistance_at_entry,
        )

    @property
    def trades(self) -> tuple:
        """The closed-trade journal in the broker's own append order.

        Returned verbatim and unsorted: the journal is append-only, so its
        order is already deterministic and chronological by entry. Reversing
        or re-sorting it here would be a transformation the engine never
        asked for.
        """

        return tuple(self._broker.journal)

    @property
    def view(self) -> SessionView:
        """Project current engine state into a serialisable snapshot."""

        return SessionView(
            service=self._service,
            session_id=self._session_id,
            mode=MODE_PAPER,
            state=STATE_IDLE,
            # No replay or execution engine exists in Phase 16B, so a session
            # is never "active". Derived, not hard-coded, so it stays correct
            # when a future phase introduces a running state.
            active=False,
            # Reused rather than recomputed: /api/session and /api/account
            # must not be able to disagree about the same figures.
            account=self.account,
            strategy=StrategyIdentity(
                config_repr=repr(self._config),
                config_hash=config_hash(self._config),
            ),
            execution=ExecutionIdentity(
                execution_model=self._costs.execution_model,
                fee_rate=self._costs.fee_rate,
                slippage_rate=self._costs.slippage_rate,
                spread_rate=self._costs.spread_rate,
                costs_repr=repr(self._costs),
                costs_hash=costs_hash(self._costs),
                risk_fraction=RISK_FRACTION,
            ),
            has_open_position=self._broker.open_trade is not None,
        )