"""Pydantic response models for the paper-trading API.

Internal Python objects are never returned from a route. Each model mirrors a
frozen dataclass in :mod:`paper_api.session`, so a change to engine-facing
state surfaces as a schema mismatch rather than as a silently reshaped payload.

Two conventions:

* ``None`` means *not available*, never zero. A field that cannot be computed
  is omitted from the model rather than reported as ``0``.
* No environment values, filesystem paths, credentials or stack traces appear
  in any model.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .session import AccountState, ExecutionIdentity, SessionView, StrategyIdentity


class _Strict(BaseModel):
    """Base model that rejects unknown keys and ignores extra input.

    ``extra="forbid"`` means a future field appearing on an internal object
    cannot leak into the payload by accident.
    """

    model_config = ConfigDict(extra="forbid")


class StrategyIdentityModel(_Strict):
    """Which strategy configuration is loaded."""

    config_repr: str = Field(
        description="Verbatim repr of the StrategyConfig in force."
    )
    config_hash: str = Field(
        description=(
            "Stable hash of the strategy config, matching the Phase 13 "
            "walk-forward record."
        )
    )


class ExecutionIdentityModel(_Strict):
    """Which execution-cost model is loaded.

    Exposed because a displayed P&L is meaningless without the cost basis that
    produced it. All values are the engine's own frozen constants.
    """

    execution_model: Literal["cost_deduction", "fill_price"]
    fee_rate: float
    slippage_rate: float
    spread_rate: float = Field(
        description="Always 0.0 under cost_deduction; the engine rejects a "
                    "non-zero spread there to prevent double counting."
    )
    costs_repr: str
    costs_hash: str
    risk_fraction: float = Field(
        description="Fraction of cash committed per position, from the "
                    "frozen walkforward.RISK_FRACTION. Not leverage: there is "
                    "no multiplier and no margin."
    )


class AccountModel(_Strict):
    """Paper account figures, read from the broker without recomputation."""

    starting_balance: float = Field(
        description="Authoritative paper starting balance "
                    "(walkforward.STARTING_BALANCE = 10000.0). Simulated "
                    "money; no real funds are represented."
    )
    balance: float = Field(
        description="Realized cash held by the broker. The engine credits "
                    "cash only when a position closes, so this excludes any "
                    "unrealized amount."
    )
    realized_pnl: float = Field(
        description="balance minus starting_balance; the same definition the "
                    "engine uses for BacktestResult.net_pnl."
    )
    trade_count: int = Field(
        ge=0, description="Closed trades in the journal. 0 in Phase 16B, "
                          "which performs no execution."
    )


class SessionResponse(_Strict):
    """Read-only snapshot of the paper session.

    Phase 16B exposes account and configuration identity only. Replay
    position, current candle, signal, unrealized P&L and statistics are
    absent because nothing in this phase can derive them; see
    ``paper_api.session.UNSUPPORTED_FIELDS``.
    """

    service: str
    session_id: str = Field(
        description="Identity of this session. Stable for the lifetime of the "
                    "session and intentionally different per process."
    )
    mode: Literal["paper"] = Field(
        description="Always 'paper'. No live, real-money or venue mode exists."
    )
    state: Literal["idle"] = Field(
        description="'idle' in Phase 16B: no replay or execution engine runs."
    )
    active: bool = Field(
        description="Whether the session is advancing. False in Phase 16B."
    )
    account: AccountModel
    strategy: StrategyIdentityModel
    execution: ExecutionIdentityModel
    has_open_position: bool = Field(
        description="Mirrors PaperBroker.open_trade. Always false in "
                    "Phase 16B, which cannot open a position."
    )
    open_position: None = Field(
        default=None,
        description="Reserved. Always null: no position can exist yet. A "
                    "Position model arrives with the execution phase.",
    )

    @classmethod
    def from_view(cls, view: SessionView) -> "SessionResponse":
        """Build a response from a session view, validating as it goes."""

        return cls(
            service=view.service,
            session_id=view.session_id,
            mode=view.mode,
            state=view.state,
            active=view.active,
            account=AccountModel(**vars(view.account)),
            strategy=StrategyIdentityModel(**vars(view.strategy)),
            execution=ExecutionIdentityModel(**vars(view.execution)),
            has_open_position=view.has_open_position,
            open_position=None,
        )


# ---------------------------------------------------------------------------
# market data (Phase 16C)
# ---------------------------------------------------------------------------


class CandleModel(_Strict):
    """One OHLCV bar, mirroring the engine's frozen ``Candle``."""

    timestamp: datetime = Field(
        description=(
            "Bar open time, serialised with an explicit +00:00 offset. The "
            "source stores naive timestamps; they are declared to be UTC "
            "rather than reinterpreted in the server's local zone."
        )
    )
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketMetadataModel(_Strict):
    """What the dashboard is looking at, without disclosing a file location."""

    asset: str
    timeframe: str
    source: str = Field(
        description="Provenance label. Never a filesystem path."
    )
    dataset_sha256: str = Field(
        description=(
            "SHA-256 of the served file, matching the frozen constant used by "
            "the Phase 13 walk-forward harness. Stable identity, not a path."
        )
    )
    dataset_candles: int = Field(
        description="Total candles in the dataset, not the returned slice."
    )
    dataset_first_timestamp: datetime
    dataset_last_timestamp: datetime
    returned_candles: int = Field(
        description="Number of candles in this response."
    )
    truncated: bool = Field(
        description=(
            "True when more candles matched the filters than ``limit`` "
            "allowed, so the most recent slice was returned."
        )
    )
    start: datetime | None = Field(
        default=None, description="Echo of the applied lower bound, if any."
    )
    end: datetime | None = Field(
        default=None, description="Echo of the applied upper bound, if any."
    )
    limit: int = Field(description="Echo of the applied candle limit.")


class MarketResponse(_Strict):
    """A read-only slice of historical candles."""

    metadata: MarketMetadataModel
    candles: list[CandleModel] = Field(
        description="Chronological, ascending, exactly as stored in the source."
    )


# ---------------------------------------------------------------------------
# strategy signal (Phase 16D)
# ---------------------------------------------------------------------------


class SignalStrategyModel(_Strict):
    """Which strategy configuration produced the signal."""

    config_hash: str = Field(
        description="Stable hash of the StrategyConfig in force."
    )
    config_repr: str


class SignalSourceModel(_Strict):
    """Which dataset the signal was computed from."""

    dataset_sha256: str
    dataset_first_timestamp: datetime
    dataset_last_timestamp: datetime


class SignalResponse(_Strict):
    """A research signal produced by ``crypto_paper_lab.strategy.analyze``.

    Every trading field maps one-to-one onto the engine's ``Signal`` model and
    is reported verbatim; the API transforms nothing and adds nothing.

    There is deliberately **no** ``confidence``, probability, expected-return
    or price-forecast field. The engine defines no such quantity, so any
    value here would be fabricated.
    """

    service: str
    asset: str
    timeframe: str

    timestamp: datetime = Field(
        description=(
            "The SIGNAL candle - the latest completed bar the strategy "
            "evaluated, serialised with an explicit +00:00 offset. This is "
            "not a fill: no execution occurred, and in the walk-forward "
            "harness a signal for this bar would be filled at the NEXT "
            "candle's open."
        )
    )

    signal: Literal["long", "short", "flat"] = Field(
        description=(
            "Engine ``Signal.side``, verbatim and lowercase. Uppercase "
            "LONG/SHORT/FLAT is a display concern for the client, not a "
            "value this API invents."
        )
    )
    reason: str = Field(
        description=(
            "One of the engine's five fixed reason strings. Not a "
            "natural-language summary."
        )
    )
    price: float = Field(
        description=(
            "``Signal.price``. For the signal candle this equals "
            "``signal_close``; the engine rewrites it to the next open only "
            "when a backtest executes a fill."
        )
    )
    support: float
    resistance: float
    trend: Literal["up", "down", "sideways"]
    breakout: bool
    retest: bool
    signal_close: float | None
    trend_state: Literal["up", "down", "sideways"] | None
    breakout_distance: float | None = Field(
        default=None,
        description="Fractional distance beyond the broken level. Null when "
                    "no breakout applied, never zero-filled.",
    )
    retest_distance: float | None = Field(
        default=None, description="Null unless this was a retest entry."
    )
    realised_volatility: float | None = Field(
        default=None,
        description="Trailing stdev of simple returns. NOT annualised, not ATR.",
    )
    mean_range: float | None = Field(
        default=None, description="Mean trailing high-low. NOT ATR."
    )

    strategy: SignalStrategyModel
    source: SignalSourceModel


# ---------------------------------------------------------------------------
# account, position and trades (Phase 16E)
# ---------------------------------------------------------------------------


class AccountResponse(_Strict):
    """Paper account state, straight from ``PaperBroker``.

    Only quantities the broker actually maintains are exposed. There is
    deliberately no available balance, reserved capital, equity, unrealized
    P&L, margin or buying power: the engine holds no margin concept, and
    equity would require an unrealized figure the engine cannot produce
    without a mark price.
    """

    starting_balance: float = Field(
        description="PaperBroker.starting_balance. Simulated money."
    )
    balance: float = Field(
        description="PaperBroker.cash. Credited only when a trade closes, so "
                    "it excludes any unrealized amount."
    )
    realized_pnl: float = Field(
        description="balance minus starting_balance - the engine's own "
                    "BacktestResult.net_pnl definition."
    )
    trade_count: int = Field(
        ge=0, description="len(PaperBroker.journal): closed trades."
    )


class PositionResponse(_Strict):
    """The open position, limited to fields the engine populates at entry."""

    side: Literal["long", "short"]
    entry_time: datetime
    entry_price: float = Field(
        description="PaperTrade.entry_price - the recorded fill."
    )
    quantity: float
    reason: str = Field(description="The triggering signal's reason string.")
    raw_entry_price: float | None = Field(
        default=None,
        description="Unadjusted reference price. Under cost_deduction this "
                    "equals entry_price; under fill_price it does not.",
    )
    signal_close: float | None
    trend_state: Literal["up", "down", "sideways"] | None
    breakout_distance: float | None
    retest_distance: float | None
    realised_volatility: float | None
    mean_range: float | None
    support_at_entry: float | None
    resistance_at_entry: float | None


class OpenPositionResponse(_Strict):
    """Envelope so "flat" is explicit rather than an absent field."""

    has_position: bool = Field(
        description="Mirrors PaperBroker.open_trade is not None."
    )
    position: PositionResponse | None


class TradeResponse(_Strict):
    """A closed trade: every ``PaperTrade`` field plus its three properties.

    ``pnl``, ``net_pnl`` and ``total_friction`` are the engine's own
    computed properties, read from the dataclass and not recalculated here.
    """

    side: Literal["long", "short"]
    entry_time: datetime
    exit_time: datetime | None
    entry_price: float
    exit_price: float | None
    quantity: float
    reason: str
    exit_reason: str
    bars_held: int
    raw_entry_price: float | None
    raw_exit_price: float | None
    costs: float = Field(
        description="Amount actually deducted from gross P&L. Under "
                    "cost_deduction this equals total_friction; under "
                    "fill_price it holds fees only."
    )
    fee_total: float
    slippage_total: float
    spread_total: float
    pnl: float | None = Field(description="PaperTrade.pnl (gross).")
    net_pnl: float | None = Field(description="PaperTrade.net_pnl.")
    total_friction: float | None = Field(
        description="PaperTrade.total_friction: fees + spread + slippage."
    )
    signal_close: float | None
    trend_state: Literal["up", "down", "sideways"] | None
    breakout_distance: float | None
    retest_distance: float | None
    realised_volatility: float | None
    mean_range: float | None
    support_at_entry: float | None
    resistance_at_entry: float | None


class TradesResponse(_Strict):
    """The closed-trade journal, in the broker's own append order."""

    trades: list[TradeResponse] = Field(
        description="Chronological by entry, exactly as PaperBroker.journal "
                    "holds them. Empty when nothing has been closed."
    )
    trade_count: int = Field(ge=0, description="len(trades).")


# ---------------------------------------------------------------------------
# statistics (Phase 16F)
# ---------------------------------------------------------------------------


class CostTotalsModel(_Strict):
    """Aggregated execution costs, from ``stats.cost_breakdown``."""

    fee_total: float
    spread_total: float = Field(
        description="Always 0.0 under cost_deduction; the engine rejects a "
                    "non-zero spread there to prevent double counting."
    )
    slippage_total: float
    total_friction: float = Field(
        description="Fees + spread + slippage. The correct cost figure "
                    "regardless of how the execution model distributes it."
    )
    deducted_costs: float = Field(
        description="Amount actually removed from gross P&L. Equals "
                    "total_friction under cost_deduction; differs under "
                    "fill_price, where spread and slippage are already inside "
                    "the fill prices."
    )


class StatisticsResponse(_Strict):
    """Closed-trade performance statistics.

    Every field is the return value of ``stats.performance`` or
    ``stats.cost_breakdown``. There is no confidence interval, risk-adjusted
    ratio or forecast.

    ``basis`` is ``closed_trades`` and is not decoration: ``stats.performance``
    excludes unrealized P&L by construction, so a panel driven by this payload
    is a *closed-trades* view. Pair it with ``/api/position``, which carries no
    unrealized figure either, rather than reading it as a live equity curve.

    ``max_drawdown`` is the **realized** drawdown over the closed-trade P&L
    sequence, as a fraction. It is not the mark-to-market drawdown; the engine
    computes that separately and it is unavailable without a candle array
    aligned to the journal. The two differ by construction, so they must never
    share a label.
    """

    service: str
    basis: Literal["closed_trades"]
    trades: int = Field(
        ge=0, description="Closed trades in the journal - stats.performance's "
                          "own count, not an estimate."
    )
    net_pnl: float = Field(description="Sum of closed-trade net P&L.")
    win_rate: float = Field(ge=0.0, le=1.0, description="A fraction, not a "
                                                       "percentage.")
    profit_factor: float | None = Field(
        description="gross_profit / gross_loss. Null when the engine reported "
                    "infinity; check profit_factor_infinite. Infinity is not "
                    "valid JSON, so it is never emitted as a number."
    )
    profit_factor_infinite: bool = Field(
        description="True when gross_loss == 0, i.e. the engine returned "
                    "float('inf'). Render as 'infinity (no losing trades)'. "
                    "Note this is also true for an empty journal, where the "
                    "ratio is vacuous rather than exceptional."
    )
    average_pnl: float = Field(description="Mean net P&L per closed trade.")
    max_drawdown: float = Field(
        ge=0.0,
        description="Realized peak-to-trough decline as a FRACTION, not a "
                    "percentage: 0.0017 means 0.17%. Not scaled here; scaling "
                    "is a display concern.",
    )
    ending_balance: float = Field(
        description="starting_balance plus net_pnl. Realized cash only."
    )
    costs: CostTotalsModel
    strategy: StrategyIdentityModel
    execution: ExecutionIdentityModel


# ---------------------------------------------------------------------------
# replay (Phase 17D)
# ---------------------------------------------------------------------------


class ReplayDatasetModel(_Strict):
    """Which historical dataset a replay is walking.

    Mirrors ``crypto_paper_lab.replay.DatasetIdentity``. A hash and declared
    bounds, never a filesystem path - the same rule ``/api/market`` follows.
    """

    asset: str
    timeframe: str
    sha256: str
    first_timestamp: datetime
    last_timestamp: datetime
    candle_count: int
    interval_seconds: int


class ReplaySignalModel(_Strict):
    """The engine ``Signal`` behind ``ReplayState.last_signal``, field for field.

    Distinct from Phase 16's ``SignalResponse`` on purpose. That model carries
    ``service``, ``asset``, ``timeframe``, ``strategy`` and ``source``, which
    describe the *request* that produced it. A replay's signal is not the product
    of a request, so including them here would mean synthesising identity the
    signal does not have.

    ``price`` is the **signal candle's close**, not the next bar's open. ``Replay``
    keeps the signal ``analyze`` returned and never rewrites it, so ``price`` and
    ``signal_close`` are equal. A consumer must not read this field as a fill.
    """

    timestamp: datetime
    side: Literal["long", "short", "flat"]
    reason: str
    price: float
    support: float
    resistance: float
    trend: Literal["up", "down", "sideways"]
    breakout: bool
    retest: bool
    signal_close: float | None
    trend_state: Literal["up", "down", "sideways"] | None
    breakout_distance: float | None
    retest_distance: float | None
    realised_volatility: float | None
    mean_range: float | None


class ReplayStateResponse(_Strict):
    """A faithful transport projection of ``crypto_paper_lab.replay.ReplayState``.

    Every field maps one-to-one onto the engine dataclass. Nothing is added,
    renamed, rounded or derived - if a number is not in ``ReplayState`` it is not
    here, and if it is in ``ReplayState`` it is here.

    Absent, because the engine cannot authoritatively produce them and inventing
    a transport field would create a second financial model: ``equity``,
    ``mark_price``, ``unrealized_pnl``, ``available_balance``,
    ``reserved_capital``, ``margin``, ``buying_power``, ``notional``,
    ``leverage`` and ``confidence``.

    Also absent: ``interval_ms``. It lives on ``Replay`` rather than on
    ``ReplayState``, and pacing is a server concern - ``status`` already says
    whether auto-run is armed.
    """

    replay_id: str = Field(
        description="Stable identity of this replay. Retained across reset, "
                    "because a reset re-runs the same configuration rather than "
                    "creating a new one."
    )
    status: Literal["idle", "running", "paused", "finished"] = Field(
        description="Lifecycle state. 'running' means armed; Phase 17D adds no "
                    "background worker, so the client drives progression through "
                    "/api/replay/step."
    )

    dataset: ReplayDatasetModel
    strategy: StrategyIdentityModel
    execution: ExecutionIdentityModel

    cursor: int = Field(
        description="Index of the **execution** bar the next step will consume. "
                    "The signal for that step is computed from candles[:cursor], "
                    "so the newest bar the strategy sees is cursor - 1."
    )
    start_index: int
    bars_processed: int = Field(description="cursor minus start_index.")

    current_timestamp: datetime | None = Field(
        default=None,
        description="Time of the last bar a step actually consumed. Null before "
                    "the first step.",
    )
    next_timestamp: datetime | None = Field(
        default=None,
        description="Time of the bar the next step will execute against. Null "
                    "once the dataset is exhausted.",
    )
    next_candle_available: bool

    starting_balance: float
    balance: float = Field(
        description="PaperBroker.cash. Realized only - the engine credits cash "
                    "on close, so this excludes any unrealized amount."
    )
    realized_pnl: float = Field(
        description="balance minus starting_balance - the engine's own "
                    "BacktestResult.net_pnl definition."
    )
    trade_count: int = Field(ge=0)

    has_open_position: bool
    open_position: PositionResponse | None = Field(
        default=None,
        description="Reuses the Phase 16 position model. Cost fields and "
                    "bars_held are omitted because PaperBroker computes them "
                    "only at close.",
    )
    last_signal: ReplaySignalModel | None = Field(
        default=None,
        description="The most recent strategy observation. Null before the first "
                    "step. Not an order and not a fill.",
    )

    @classmethod
    def from_state(cls, state) -> "ReplayStateResponse":
        """Build a response from an engine ``ReplayState``.

        Timestamps are converted to aware UTC by the caller's helper so the
        wire format matches every other Phase 16 endpoint. The engine keeps naive
        UTC and is not modified.
        """

        from .marketdata import as_utc

        signal = state.last_signal

        return cls(
            replay_id=state.replay_id,
            status=state.status,
            dataset=ReplayDatasetModel(
                asset=state.dataset.asset,
                timeframe=state.dataset.timeframe,
                sha256=state.dataset.sha256,
                first_timestamp=as_utc(state.dataset.first_timestamp),
                last_timestamp=as_utc(state.dataset.last_timestamp),
                candle_count=state.dataset.candle_count,
                interval_seconds=state.dataset.interval_seconds,
            ),
            strategy=StrategyIdentityModel(**vars(state.strategy)),
            execution=ExecutionIdentityModel(**vars(state.execution)),
            cursor=state.cursor,
            start_index=state.start_index,
            bars_processed=state.bars_processed,
            current_timestamp=(
                as_utc(state.current_timestamp)
                if state.current_timestamp is not None
                else None
            ),
            next_timestamp=(
                as_utc(state.next_timestamp)
                if state.next_timestamp is not None
                else None
            ),
            next_candle_available=state.next_candle_available,
            starting_balance=state.starting_balance,
            balance=state.balance,
            realized_pnl=state.realized_pnl,
            trade_count=state.trade_count,
            has_open_position=state.has_open_position,
            open_position=(
                PositionResponse(
                    side=state.open_position.side,
                    entry_time=as_utc(state.open_position.entry_time),
                    entry_price=state.open_position.entry_price,
                    quantity=state.open_position.quantity,
                    reason=state.open_position.reason,
                    raw_entry_price=state.open_position.raw_entry_price,
                    signal_close=state.open_position.signal_close,
                    trend_state=state.open_position.trend_state,
                    breakout_distance=state.open_position.breakout_distance,
                    retest_distance=state.open_position.retest_distance,
                    realised_volatility=state.open_position.realised_volatility,
                    mean_range=state.open_position.mean_range,
                    support_at_entry=state.open_position.support_at_entry,
                    resistance_at_entry=state.open_position.resistance_at_entry,
                )
                if state.open_position is not None
                else None
            ),
            last_signal=(
                ReplaySignalModel(
                    timestamp=as_utc(signal.timestamp),
                    side=signal.side,
                    reason=signal.reason,
                    price=signal.price,
                    support=signal.support,
                    resistance=signal.resistance,
                    trend=signal.trend,
                    breakout=signal.breakout,
                    retest=signal.retest,
                    signal_close=signal.signal_close,
                    trend_state=signal.trend_state,
                    breakout_distance=signal.breakout_distance,
                    retest_distance=signal.retest_distance,
                    realised_volatility=signal.realised_volatility,
                    mean_range=signal.mean_range,
                )
                if signal is not None
                else None
            ),
        )