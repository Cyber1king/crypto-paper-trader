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

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crypto_paper_lab.high_risk import MAX_RISK_FRACTION

from .highrisksession import HIGH_RISK_LABEL
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
# modes (Phase 17F)
# ---------------------------------------------------------------------------


class ModeInfoModel(_Strict):
    """Configuration of one paper mode. Identity only, never trading state.

    Deliberately carries no balance, cursor, journal, position or P&L. A mode is
    a name, a policy and a capability; anything that changes as it runs belongs to
    its broker and is read from ``/api/replay?mode=...``.
    """

    mode: str = Field(description="Stable mode identifier used in requests.")
    label: str = Field(description="Human-facing name. Cosmetic; never a lookup key.")
    supports_execution: bool = Field(
        description="Whether this mode may execute paper trades at all. False for "
                    "Alerts, which holds no broker, so execution is not merely "
                    "switched off but unrepresentable."
    )
    available: bool = Field(
        description="Whether the mode can be used yet. A reserved mode is "
                    "recognised and refused rather than silently treated as "
                    "Standard."
    )
    note: str = Field(
        description="Why the mode is unavailable, or what it will become. Surfaced "
                    "so a client can explain itself instead of guessing."
    )
    policy: dict | None = Field(
        default=None,
        description="Identity of the policy this mode decides with, or null for a "
                    "mode with no policy because it cannot execute."
    )


class ModesResponse(_Strict):
    """Every recognised mode. Read-only discovery; holds no session state."""

    default_mode: str = Field(
        description="Mode selected when a request omits one."
    )
    modes: list[ModeInfoModel] = Field(
        description="All modes, available or reserved. Reserved entries are "
                    "included so a client can tell 'not built yet' from 'no such "
                    "mode'."
    )


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


class ScoreComponentModel(_Strict):
    """One explained contribution to an intelligence score.

    Mirrors ``crypto_paper_lab.intelligence.ScoreComponent``. ``points`` is what the
    component contributed and ``weight`` is the most it could have, so a client can
    show *why* a score is what it is without reimplementing the scorer.
    """

    name: str
    points: float
    weight: float
    reason: str = Field(
        description="Plain-language explanation built from the same numbers as "
                    "points, so the score can be audited by hand."
    )


class IntelligenceModel(_Strict):
    """A deterministic intelligence score and its qualification verdict.

    Mirrors ``crypto_paper_lab.intelligence.IntelligenceScore``.

    This is a **research heuristic**, not a probability, a win rate, an expected
    return or any profit forecast. ``qualified`` means only that the score reached
    the configured threshold.
    """

    score: int = Field(
        ge=0,
        le=100,
        description="Score on the fixed 0-100 scale. Not a probability.",
    )
    threshold: float = Field(
        description="Threshold this score was compared against."
    )
    qualified: bool = Field(
        description="score >= threshold. True does not imply a profitable trade."
    )
    side: Literal["long", "short", "flat"]
    components: list[ScoreComponentModel] = Field(
        description="Every component with its own explanation. Sums to the score."
    )


class AiPositionModel(_Strict):
    """One AI paper position, open or closed.

    Mirrors ``crypto_paper_lab.ai_paper.AiPosition``.

    ``position_id`` is a monotonic counter (``ai-1``, ``ai-2``, ...), not a UUID, so
    a run is reproducible and the journal reads in order. ``allocated_capital`` is
    the paper cash this position holds, which is released on close.

    Exit fields are null while the position is open: ``PaperBroker`` computes cost
    and exit price only at close, and reporting zeros would claim an open trade
    cost nothing.
    """

    position_id: str
    side: Literal["long", "short"]
    state: Literal["open", "closed"]
    entry_index: int
    entry_timestamp: datetime
    entry_price: float
    quantity: float
    allocated_capital: float
    reason: str
    intelligence_score: int = Field(
        description="Score that admitted this signal, retained so a closed "
                    "position can be audited without re-deriving it."
    )
    qualification_threshold: float

    exit_index: int | None = None
    exit_timestamp: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    bars_held: int | None = None
    realized_pnl: float | None = Field(
        default=None,
        description="The engine's net_pnl: gross P&L minus costs. Null while open.",
    )
    costs: float | None = None

    @classmethod
    def from_position(cls, position) -> "AiPositionModel":
        from .marketdata import as_utc

        return cls(
            position_id=position.position_id,
            side=position.side,
            state=position.state,
            entry_index=position.entry_index,
            entry_timestamp=as_utc(position.entry_timestamp),
            entry_price=position.entry_price,
            quantity=position.quantity,
            allocated_capital=position.allocated_capital,
            reason=position.reason,
            intelligence_score=position.intelligence_score,
            qualification_threshold=position.qualification_threshold,
            exit_index=position.exit_index,
            exit_timestamp=(
                as_utc(position.exit_timestamp)
                if position.exit_timestamp is not None
                else None
            ),
            exit_price=position.exit_price,
            exit_reason=position.exit_reason,
            bars_held=position.bars_held,
            realized_pnl=position.realized_pnl,
            costs=position.costs,
        )


class AiAccountModel(_Strict):
    """AI Intelligence's capital accounting. Mirrors ``AiAccountState``.

    Absent by design, because the engine has no live price feed and cannot
    authoritatively produce them: ``equity``, ``mark_price``, ``unrealized_pnl``,
    ``margin``, ``buying_power`` and ``leverage``. There is no leverage and no
    margin in this mode; ``available_capital`` is capital bookkeeping, not
    buying power.
    """

    starting_capital: float
    committed_capital: float = Field(
        description="Allocated capital held by open positions. Released on close."
    )
    realized_balance: float
    available_capital: float = Field(
        description="realized_balance minus committed_capital. What a new position "
                    "could still commit."
    )
    realized_pnl: float = Field(
        description="realized_balance minus starting_capital."
    )
    open_position_count: int = Field(ge=0)
    max_positions: int = Field(ge=1)
    position_allocation: float = Field(
        description="Capital per position: starting_capital divided by "
                    "max_positions."
    )
    signals_qualified: int = Field(
        ge=0,
        description="Signals that reached the threshold, whether or not they found "
                    "room. Counted because a mode that silently drops signals is "
                    "indistinguishable from one that saw none."
    )
    signals_admitted: int = Field(ge=0)
    signals_declined: int = Field(ge=0)

    @classmethod
    def from_state(cls, state) -> "AiAccountModel":
        return cls(**vars(state))


class AiStateResponse(_Strict):
    """AI Intelligence's authoritative mode state.

    Two sources, kept clearly separate because they answer different questions:

    * ``account`` and ``positions`` are the AI contract - capital, positions and
      realised P&L, all read from ``AiPaperBook``.
    * ``replay`` is the shared Phase 17D replay state: cursor, lifecycle status,
      dataset and strategy identity. Present because a client needs to know where
      the mode is in the dataset, and identical in shape to every other mode's.

    Everything here is a projection. This module computes no score, no quantity,
    no exit and no P&L.
    """

    mode: str = Field(
        default="ai_intelligence",
        description="Always 'ai_intelligence'. This response describes no other "
                    "mode; the AI contract exists for this one mode only.",
    )
    account: AiAccountModel
    positions: list[AiPositionModel] = Field(
        description="Every position in entry order, open or closed."
    )
    journal: list[AiPositionModel] = Field(
        description="Closed positions in close order."
    )
    last_score: IntelligenceModel | None = Field(
        default=None,
        description="The most recent signal's score, or null before the first "
                    "step. Null is honest rather than zero: no signal has been "
                    "observed yet."
    )
    replay: ReplayStateResponse = Field(
        description="The shared replay state: cursor, status, identities. Carries "
                    "'mode' = 'ai_intelligence' because that is genuinely which "
                    "mode produced it."
    )

    @classmethod
    def from_ai(cls, session, score=None) -> "AiStateResponse":
        """Build from an :class:`~paper_api.moderegistry.AiSession`.

        ``score`` is the session's authoritative last score. It is passed in rather
        than recomputed here, because a transport that re-ran the scorer would be a
        second scoring implementation.
        """

        from .marketdata import as_utc

        resolved_score = (
            score if score is not None else session.book.last_score
        )

        return cls(
            mode="ai_intelligence",
            account=AiAccountModel.from_state(session.ai_state),
            positions=[
                AiPositionModel.from_position(position)
                for position in session.book.positions
            ],
            journal=[
                AiPositionModel.from_position(position)
                for position in session.book.journal
            ],
            last_score=(
                IntelligenceModel(
                    score=resolved_score.score,
                    threshold=resolved_score.threshold,
                    qualified=resolved_score.qualified,
                    side=resolved_score.side,
                    components=[
                        ScoreComponentModel(
                            name=component.name,
                            points=component.points,
                            weight=component.weight,
                            reason=component.reason,
                        )
                        for component in resolved_score.components
                    ],
                )
                if resolved_score is not None
                else None
            ),
            replay=ReplayStateResponse.from_state(
                session.snapshot(), mode="ai_intelligence"
            ),
        )


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

    #: Which mode produced this state.
    mode: str = Field(
        default="standard",
        description="Paper mode this state belongs to. Omitting the parameter "
                    "selects Standard, so a request that never mentions modes "
                    "behaves exactly as it did before they existed.",
    )

    @classmethod
    def from_state(cls, state, mode: str = "standard") -> "ReplayStateResponse":
        """Build a response from an engine ``ReplayState``.

        ``mode`` is echoed from the request rather than derived, because a replay
        has no opinion about which mode asked for it - the registry does, and the
        transport passes the selection through.
        """

        from .marketdata import as_utc

        signal = state.last_signal

        return cls(
            mode=mode,
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


# ---------------------------------------------------------------------------
# Phase 24B/24C. Daily Target
# ---------------------------------------------------------------------------


class DailyTargetConfigRequest(_Strict):
    """The body of ``POST /api/daily-target/config``.

    Deliberately one field. The product contract is "I want to make N dollars today",
    so the request expresses exactly that and nothing about percentage, basis or
    compounding - every one of which was a way of making the target depend on the
    account balance rather than on the user's decision.

    Validation lives in :class:`~crypto_paper_lab.daily_target.DailyTargetConfig`,
    not here, for one reason: the engine must reject a bad target whether it arrives
    over HTTP or from Python. A transport-only check would leave
    ``DailyTargetTracker.set_target`` callable with nonsense by any other caller, and
    the route would then be validating something the engine had already accepted.

    The bounds declared here are therefore only what Pydantic must enforce to produce
    a typed ``NaN``/``infinity`` payload at all; the substantive limits (finite,
    ``> 0``, at most :data:`~crypto_paper_lab.daily_target.MAX_TARGET_AMOUNT`) are
    asserted by the engine and surface as a 422 carrying the engine's own wording.
    """

    target_amount: float = Field(
        description="The daily objective in dollars of realized paper P&L. Must be "
                    "finite and greater than 0. Rejected, never clamped."
    )

    @field_validator("target_amount", mode="before")
    @classmethod
    def _reject_non_numeric(cls, value: object) -> object:
        """Refuse a ``bool`` before Pydantic coerces it.

        Python's ``bool`` is a subclass of ``int``, so Pydantic turns ``true`` into
        ``1.0`` and the mode would quietly accept a **$1.00** target that the client
        never asked for. A target is a price; accepting a type that means "yes" for it
        is exactly the silent coercion this contract refuses to do anywhere else, so
        it is rejected at the edge.

        Numbers are passed through untouched - including a float ``nan`` or
        ``inf``, which the engine then rejects with its own wording.
        """

        if isinstance(value, bool):
            raise ValueError(
                "target_amount must be a number of dollars, not a boolean"
            )

        return value


class DailyResultModel(_Strict):
    """One finalized UTC day's outcome.

    Present so the day history is a record a client can render, not a claim. Every
    figure is broker-owned or config-derived; the transport computes none of them.
    """

    date: str = Field(description="The UTC calendar date this day covered.")
    starting_balance: float = Field(
        description="Equity when the day opened: the carried paper cash, never a "
                    "reset to the mode's opening figure."
    )
    realized_pnl: float = Field(
        description="Realized paper P&L for the day, after costs. Never includes an "
                    "unrealized amount."
    )
    target_amount: float = Field(
        description="The dollar objective that applied ON THIS DAY. Recorded per day "
                    "because the user may change the target mid-run, so a past day is "
                    "reported against the target it was actually measured against."
    )
    remaining: float = Field(
        description="max(target_amount - realized_pnl, 0) for this day. Never "
                    "negative."
    )
    reached: bool
    trades_closed: int = Field(ge=0)

    @classmethod
    def from_result(cls, result) -> "DailyResultModel":
        """A straight projection of an engine-owned finalized day.

        Every field comes from :meth:`DailyResult.identity`, including ``remaining``:
        the arithmetic is done once in the engine, when the day is recorded, so this
        cannot drift from the live figure.
        """

        return cls(**result.identity())


class DailyTargetResponse(_Strict):
    """Daily Target's authoritative daily state. A projection, nothing more.

    **It computes nothing.** Every figure is read from the engine's
    :class:`~crypto_paper_lab.daily_target.DailyTargetTracker` and its
    ``PaperBroker``. No score, no quantity, no exit, no P&L and no mark-to-market
    value is derived here; the engine has no live price feed, so an unrealized figure
    is not merely omitted but unrepresentable.

    ``state`` is ``None`` before the replay's first step, and so is everything derived
    from it. That is the Phase 16 convention - *None* means *not available*, never
    zero - and it is why no field below is defaulted to a number that would read as a
    measured value the engine has not produced.
    """

    mode: Literal["daily_target"] = "daily_target"

    daily_target_amount: float = Field(
        gt=0,
        description="Today's objective in DOLLARS of realized paper P&L. A fixed "
                    "amount the user chose, independent of the account balance and "
                    "unchanged across UTC day boundaries. This is the contract: there "
                    "is no target percentage, and the $10,000 demo balance does not "
                    "determine it."
    )

    target_note: str = Field(
        description="The non-guarantee statement, reused verbatim from the engine so "
                    "the API and the UI cannot drift into different claims."
    )

    waiting_note: str = Field(
        description="States that the target is an objective rather than a signal, so "
                    "a client cannot imply the mode trades to reach it."
    )

    overshoot_note: str = Field(
        description="Why the target may be exceeded: realized P&L moves in whole "
                    "trades."
    )

    overshoot_possible: bool = Field(
        description="Always true. Present so a client cannot present the target as a "
                    "precise threshold without the response saying otherwise."
    )

    current_date: str | None = Field(
        default=None,
        description="The UTC calendar day being tracked, or null before the first "
                    "step.",
    )
    day_starting_balance: float | None = Field(
        default=None,
        description="Equity when the current day opened: the carried paper cash.",
    )
    realized_daily_pnl: float | None = Field(
        default=None,
        description="Realized paper P&L for the current day, after costs. Never "
                    "unrealized.",
    )
    remaining: float | None = Field(
        default=None,
        description="max(daily_target_amount - realized_daily_pnl, 0). Never "
                    "negative. Null before the first step.",
    )
    progress: float | None = Field(
        default=None,
        description="realized_daily_pnl / daily_target_amount. May exceed 1.0 when a "
                    "trade overshoots. Null before the first step.",
    )
    target_reached: bool | None = Field(
        default=None,
        description="Whether today's realized P&L has reached target_amount. False "
                    "before any close, because nothing has been realized yet.",
    )

    target_changed_during_day: bool = Field(
        default=False,
        description="True when the user changed the target while this day was open, so "
                    "a client can say the figure is a mix of two objectives rather "
                    "than silently reporting one of them.",
    )

    days_completed: list[DailyResultModel] = Field(
        default_factory=list,
        description="Finalized UTC days in chronological order. The current day is "
                    "never included.",
    )

    replay: ReplayStateResponse = Field(
        description="The shared replay state: cursor, status, identities. The daily "
                    "account is above; the paper broker figures are Standard's own "
                    "endpoints, unchanged."
    )

    @classmethod
    def from_session(cls, session, state, replay_state) -> "DailyTargetResponse":
        """Build from a :class:`~paper_api.moderegistry.DailyTargetSession`.

        ``state`` is the tracker's projection, passed in rather than recomputed: a
        transport that re-derived progress from a balance would be a second
        accounting implementation, which is exactly what Phase 17G ruled out for
        scoring.
        """

        from crypto_paper_lab.daily_target import (
            OVERSHOOT_NOTE,
            TARGET_NOTE,
            WAITING_NOTE,
        )

        return cls(
            # Read from the configuration, not from ``state``: the target is a user
            # setting and must be reportable on an idle replay that has never stepped,
            # so a user can see and change the goal before trading begins.
            daily_target_amount=session.daily_config.target_amount,
            target_note=TARGET_NOTE,
            waiting_note=WAITING_NOTE,
            overshoot_note=OVERSHOOT_NOTE,
            overshoot_possible=True,
            target_changed_during_day=session.daily_target_changed_during_day,
            current_date=(
                state.current_date.isoformat() if state is not None else None
            ),
            day_starting_balance=(
                state.day_starting_balance if state is not None else None
            ),
            realized_daily_pnl=(
                state.realized_daily_pnl if state is not None else None
            ),
            remaining=(state.remaining if state is not None else None),
            progress=(state.progress if state is not None else None),
            target_reached=(state.target_reached if state is not None else None),
            days_completed=[
                DailyResultModel.from_result(result)
                for result in (state.days_completed if state is not None else ())
            ],
replay=ReplayStateResponse.from_state(replay_state, mode="daily_target"),
        )


# ---------------------------------------------------------------------------
# Phase 25B. Manual
# ---------------------------------------------------------------------------


class ManualActionRequest(_Strict):
    """The body of ``POST /api/manual/action``.

    Two fields, and one of them conditional. ``size_pct`` is required for an entry and
    **refused** for an exit: silently ignoring a size on an exit would hide a request
    the user did not mean, which is the one thing a paper tool must not do.

    It is a **fraction of cash**, not a quantity and not a notional. The engine derives
    the quantity from its own fill price inside ``PaperBroker.open_from_signal``, so a
    number the transport computed could disagree with the fill it was priced against.
    Fraction in, engine-owned quantity out.

    Substantive validation lives in
    :func:`~crypto_paper_lab.manual_paper.coerce_size_pct`, for the same reason Daily
    Target's does: the engine must reject a bad size whether it arrives over HTTP or
    from Python.
    """

    action: str = Field(
        description="One of ENTER_LONG, ENTER_SHORT, EXIT. Case-insensitive. HOLD is "
                    "not an action and REVERSE is not supported."
    )

    size_pct: float | None = Field(
        default=None,
        description="Fraction of paper cash to commit, greater than 0 and at most 1. "
                    "Required for an entry; rejected for an exit. Never clamped.",
    )

    @field_validator("size_pct", mode="before")
    @classmethod
    def _reject_non_numeric(cls, value: object) -> object:
        """Refuse a ``bool`` and a non-number before Pydantic coerces them.

        ``bool`` is an ``int`` subclass, so Pydantic turns ``true`` into ``1.0`` and the
        mode would silently commit the **entire account** to a request that never
        mentioned a size. That is the worst available failure for this field, so it is
        refused at the edge rather than reaching the engine as a plausible-looking 1.0.
        """

        if isinstance(value, bool):
            raise ValueError("size_pct must be a fraction, not a boolean")

        return value


class ManualIntentModel(_Strict):
    """The action waiting for a bar, or the absence of one.

    ``None`` is honest: there is no pending action, which is the ordinary state between
    two user decisions. It is not defaulted to a placeholder action, which would render
    a control the engine has no intention of filling.
    """

    action: str = Field(description="The requested action.")
    size_pct: float | None = Field(
        default=None, description="The requested fraction of cash, for an entry."
    )

    @classmethod
    def from_intent(cls, intent) -> "ManualIntentModel":
        return cls(action=intent.action, size_pct=intent.size_pct)


class ManualPositionModel(_Strict):
    """Manual's open paper position.

    A projection of the engine's own ``PaperTrade``, so every figure here was computed
    by :class:`~crypto_paper_lab.simulator.PaperBroker`. The strategy instrumentation
    fields are present because they are part of the trade, and they are ``None`` for a
    manual entry — there is no signal behind a user's decision, so recording a trend or
    a breakout distance would be inventing data the engine never produced.
    """

    side: str = Field(description="long or short.")
    entry_time: datetime = Field(description="When the position filled.")
    entry_price: float = Field(description="Price actually paid, after fill costs.")
    raw_entry_price: float | None = Field(
        default=None,
        description="Unadjusted reference price from the execution bar. Identical to "
                    "entry_price under the cost_deduction execution model.",
    )
    quantity: float = Field(description="Units, derived by the broker.")
    reason: str = Field(description="Why the position was opened.")

    signal_close: float | None = None
    trend_state: str | None = None
    breakout_distance: float | None = None
    retest_distance: float | None = None
    realised_volatility: float | None = None
    mean_range: float | None = None
    support_at_entry: float | None = None
    resistance_at_entry: float | None = None

    @classmethod
    def from_trade(cls, trade) -> "ManualPositionModel":
        return cls(
            side=trade.side,
            entry_time=trade.entry_time,
            entry_price=trade.entry_price,
            raw_entry_price=trade.raw_entry_price,
            quantity=trade.quantity,
            reason=trade.reason,
            signal_close=trade.signal_close,
            trend_state=trade.trend_state,
            breakout_distance=trade.breakout_distance,
            retest_distance=trade.retest_distance,
            realised_volatility=trade.realised_volatility,
            mean_range=trade.mean_range,
            support_at_entry=trade.support_at_entry,
            resistance_at_entry=trade.resistance_at_entry,
        )


class ManualTradeModel(_Strict):
    """One closed manual paper trade.

    ``pnl``, ``costs`` and ``net_pnl`` are the broker's own properties, serialised as
    values. The transport does not recompute them: a second implementation of the
    engine's P&L definition is exactly the drift this project exists to prevent.
    """

    side: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime | None
    exit_price: float | None
    raw_entry_price: float | None = None
    raw_exit_price: float | None = None
    quantity: float
    reason: str
    exit_reason: str
    bars_held: int = Field(ge=0)

    pnl: float | None = Field(default=None, description="Gross P&L before costs.")
    costs: float = Field(description="Fees plus slippage, as deducted.")
    net_pnl: float | None = Field(
        default=None, description="P&L after the deducted costs."
    )
    fee_total: float = 0.0
    slippage_total: float = 0.0
    spread_total: float = 0.0
    total_friction: float | None = Field(
        default=None, description="Fees plus spread plus slippage."
    )

    @classmethod
    def from_trade(cls, trade) -> "ManualTradeModel":
        return cls(
            side=trade.side,
            entry_time=trade.entry_time,
            entry_price=trade.entry_price,
            exit_time=trade.exit_time,
            exit_price=trade.exit_price,
            raw_entry_price=trade.raw_entry_price,
            raw_exit_price=trade.raw_exit_price,
            quantity=trade.quantity,
            reason=trade.reason,
            exit_reason=trade.exit_reason,
            bars_held=trade.bars_held,
            pnl=trade.pnl,
            costs=trade.costs,
            net_pnl=trade.net_pnl,
            fee_total=trade.fee_total,
            slippage_total=trade.slippage_total,
            spread_total=trade.spread_total,
            total_friction=trade.total_friction,
        )


class ManualStateResponse(_Strict):
    """Manual's authoritative paper state. A projection, nothing more.

    **It computes nothing.** Every figure is read from
    :class:`~crypto_paper_lab.simulator.PaperBroker` or is the engine's own
    ``cash - starting_balance``. No fill is derived here, no notional is estimated
    here and no P&L is recomputed here; if this route computed any of them it would be a
    second accounting truth that could disagree with the broker that decided when to
    fill.

    Served **only** from ``/api/manual``. Nothing on this model appears on
    ``/api/account``, ``/api/position``, ``/api/trades``, ``/api/statistics`` or
    ``/api/ai``, which keep describing Standard.
    """

    mode: Literal["manual"] = "manual"

    note: str = Field(
        description="The paper-only statement, reused verbatim from the engine so the "
                    "API and the UI cannot drift into different claims."
    )

    #: Which actions the engine would accept right now, derived from state rather than
    #: hard-coded, so the UI cannot offer a button that would be refused.
    available_actions: list[str] = Field(
        default_factory=list,
        description="Action names currently permitted. Empty when the replay is "
                    "finished, has no bar left, or has no cash to commit.",
    )

    pending_action: ManualIntentModel | None = Field(
        default=None,
        description="The action waiting for a bar, or null. An action is an INTENT: it "
                    "fills at the next execution candle's open when the replay "
                    "steps.",
    )

    paper_note: str | None = Field(
        default=None,
        description="Set when a pending action was replaced or dropped, so a request "
                    "the user made is never swallowed silently.",
    )

    paper_cash: float = Field(
        description="broker.cash. Not equity: the engine values no open position and "
                    "reports no unrealized amount."
    )
    starting_balance: float
    realized_pnl: float = Field(
        description="cash - starting_balance, the engine's own definition."
    )
    trade_count: int = Field(ge=0)

    open_position: ManualPositionModel | None = Field(
        default=None, description="The open paper position, or null."
    )

    #: Bars the open position has been held. Null when flat.
    bars_held: int | None = Field(
        default=None,
        ge=0,
        description="cursor - the bar the position filled against. Computed by the "
                    "session because the engine writes a trade's own bars_held only "
                    "at close, where it reports 0 while the position is open.",
    )

    journal: list[ManualTradeModel] = Field(
        default_factory=list, description="Closed manual trades, newest first."
    )

    execution_price_preview: float | None = Field(
        default=None,
        description="The next execution candle's OPEN. A PREVIEW and explicitly not a "
                    "fill price: it is where a pending action would fill if the replay "
                    "steps now, and the realised fill is the broker's own.",
    )

    execution_bar_timestamp: datetime | None = Field(
        default=None, description="The timestamp of that execution candle."
    )

    max_size_pct: float = Field(
        description="The largest fraction of cash this session will accept. Rejected "
                    "requests are refused, never clamped to it."
    )

    preview_note: str = Field(
        description="The wording a UI must show beside the preview, so the price can "
                    "never be read as guaranteed."
    )

    replay: ReplayStateResponse = Field(
        description="The shared replay state: cursor, status, identities."
    )

    @classmethod
    def from_session(cls, session) -> "ManualStateResponse":
        """Build from a :class:`~paper_api.manualsession.ManualSession`.

        The session's own projection is passed through rather than recomputed here, for
        the same reason ``DailyTargetResponse.from_session`` does: a transport that
        re-derived progress would be a second accounting implementation.
        """

        from crypto_paper_lab.manual_paper import MANUAL_NOTE, PREVIEW_NOTE

        state = session.manual_state()

        return cls(
            note=MANUAL_NOTE,
            available_actions=list(state.available_actions),
            pending_action=(
                ManualIntentModel.from_intent(state.pending_action)
                if state.pending_action is not None
                else None
            ),
            paper_note=state.dropped_intent_reason,
            paper_cash=state.paper_cash,
            starting_balance=state.starting_balance,
            realized_pnl=state.realized_pnl,
            trade_count=state.trade_count,
            open_position=(
                ManualPositionModel.from_trade(state.open_position)
                if state.open_position is not None
                else None
            ),
            bars_held=state.bars_held,
            journal=[ManualTradeModel.from_trade(trade) for trade in state.journal],
            execution_price_preview=state.execution_price_preview,
            execution_bar_timestamp=state.execution_bar_timestamp,
            max_size_pct=session.manual_config.max_size_pct,
            preview_note=PREVIEW_NOTE,
            replay=ReplayStateResponse.from_state(state.replay, mode="manual"),
        )


# ---------------------------------------------------------------------------
# Phase 26B. High-Risk
# ---------------------------------------------------------------------------


class HighRiskConfigRequest(_Strict):
    """The body of ``POST /api/high-risk/config``.

    Exactly one field, and it is the whole mode.

    ``risk_fraction`` is a **fraction of current paper cash**, not a quantity and
    not a notional. The engine derives the quantity inside
    ``PaperBroker.open_from_signal`` from its own fill price, so a number the
    transport computed could disagree with the fill it was priced against.
    Fraction in, engine-owned quantity out - which is also what keeps exposure
    bounded by cash without this transport having to know a price.

    Typed as ``float`` and **not** constrained here. The authoritative range
    check lives in :func:`crypto_paper_lab.high_risk.coerce_risk_fraction`, which
    is where the ceiling and the wording live; duplicating the bounds in a
    Pydantic constraint would give two places to change and let the two drift.
    ``extra="forbid"`` still applies, so an unknown field is a 422 rather than a
    silently ignored key.

    Accepted range: finite, ``> 0``, ``<= 1.0``. The ``<= 1.0`` ceiling is the
    broker's own and is what makes leverage unreachable; out-of-range values are
    **refused, never clamped**, because a silently trimmed size would commit a
    position the user did not ask for.
    """

    risk_fraction: float = Field(
        description="Share of current paper cash to commit to each position, as a "
                    "fraction. Must be finite and greater than 0, and at most "
                    f"{MAX_RISK_FRACTION} - a larger value would require more "
                    "capital than the paper account holds. Rejected, never clamped."
    )

    @field_validator("risk_fraction", mode="before")
    @classmethod
    def _reject_non_numeric(cls, value: object) -> object:
        """Refuse a ``bool`` and a non-numeric string before Pydantic coerces them.

        ``bool`` is an ``int`` subclass, so Pydantic would turn ``true`` into
        ``1.0`` - the maximum legal size - and this mode would commit the whole
        paper account to a request that never mentioned a fraction. That is the
        worst failure available for this field, so it is refused at the edge rather
        than reaching the engine as a plausible-looking maximum.

        A **numeric string** is refused too, and that is stricter than Pydantic's
        default. In lax mode ``"0.3"`` becomes the float ``0.3``, so a JSON client
        sending a quoted number would be silently accepted. The value has one
        correct representation here, and accepting two would mean the API and the
        UI could disagree about what was actually configured.

        This mirrors ``ManualActionRequest._reject_non_numeric``, so the two modes
        handle a boolean identically rather than one guarding and one not.
        """

        if isinstance(value, bool):
            raise ValueError("risk_fraction must be a fraction, not a boolean")

        if isinstance(value, str):
            raise ValueError(
                "risk_fraction must be a JSON number, not a string; a quoted "
                "number would be silently accepted as a different value"
            )

        return value


class HighRiskStateResponse(_Strict):
    """High-Risk's authoritative paper state.

    Served **only** from ``/api/high-risk``. No field of this model appears on
    ``/api/account``, ``/api/position``, ``/api/trades``, ``/api/statistics``,
    ``/api/replay``, ``/api/ai``, ``/api/manual`` or ``/api/daily-target``, all
    of which keep describing their own modes.

    Every money figure is the broker's own. ``exposure`` and ``exposure_fraction``
    are the one derived pair, and they are the arithmetic identity
    ``entry_price * quantity`` of two fields :class:`PaperBroker` already owns -
    computed in the session so no client has to, and satisfying
    ``exposure <= paper_cash`` because the broker refuses any
    ``risk_fraction > 1.0`` before it sizes anything.

    Absent by design, because the engine cannot authoritatively produce them:
    equity, mark price, unrealized P&L, margin, buying power, reserved capital,
    liquidation price, leverage.
    """

    mode: str = Field(description="Always 'high_risk'.")

    label: str = Field(
        description="Human-facing mode name. Carries 'Paper Trading' so the mode "
                    "never appears without the word that says what it is."
    )

    available: bool = Field(description="Whether the mode is usable.")

    risk_fraction: float = Field(
        description="Share of current paper cash committed to each position right "
                    "now. Applies to the next entry."
    )

    max_risk_fraction: float = Field(
        description="The engine's hard ceiling. Exposure cannot exceed paper cash, "
                    "so this is the largest position the mode can take."
    )

    paper_cash: float = Field(
        description="PaperBroker.cash. Not equity: the engine values no open "
                    "position, and cash is never debited on entry."
    )

    starting_balance: float = Field(description="PaperBroker.starting_balance.")

    realized_pnl: float = Field(
        description="cash - starting_balance, the engine's own definition. Never "
                    "includes an unrealized amount."
    )

    trade_count: int = Field(description="Entries in PaperBroker.journal.")

    open_position: PositionResponse | None = Field(
        default=None,
        description="The open paper trade, or null. Always at most one.",
    )

    exposure: float = Field(
        description="entry_price * quantity of the open trade, or 0.0 when flat. "
                    "Never greater than paper_cash."
    )

    exposure_fraction: float = Field(
        description="exposure / paper_cash, or 0.0 when flat or with no cash."
    )

    position_count: int = Field(
        description="0 or 1. PaperBroker holds one open_trade, so this can never "
                    "exceed one."
    )

    max_positions: int = Field(
        description="The policy's position limit. 1, and it is the broker's own "
                    "single-position rule rather than a policy preference."
    )

    exit_counts: dict[str, int] = Field(
        description="Tally of closed trades by exit reason. The frozen baseline "
                    "produces only 'opposite_signal' and 'end_of_data'."
    )

    last_signal: ReplaySignalModel | None = Field(
        default=None,
        description="The strategy's most recent observation. 'flat' is a normal "
                    "outcome, not an error. High-Risk adds no qualification rule, "
                    "so this is exactly the signal Standard saw at this cursor."
    )

    inherits_note: str = Field(
        description="The scope statement, served so a client cannot drop it: "
                    "High-Risk introduces no new signal qualification rule and "
                    "inherits Standard's signal set."
    )

    note: str = Field(
        description="What this mode is, and what 'high risk' means here: more "
                    "paper capital per position, never leverage."
    )

    caution: str = Field(
        description="The measured friction warning. Costs grow with position "
                    "size and at the maximum setting exceed the strategy's gross "
                    "result on the frozen dataset."
    )

    replay: ReplayStateResponse = Field(
        description="The shared replay state: cursor, status, identities."
    )

    @classmethod
    def from_session(cls, session) -> "HighRiskStateResponse":
        """Build from a :class:`~paper_api.highrisksession.HighRiskSession`.

        The session's own projection is passed through rather than recomputed
        here, for the same reason ``ManualStateResponse.from_session`` and
        ``DailyTargetResponse.from_session`` do: a transport that re-derived
        exposure or realized P&L would be a second accounting implementation.
        """

        from crypto_paper_lab.high_risk import HIGH_RISK_NOTE
        from crypto_paper_lab.modes import HIGH_RISK as HIGH_RISK_MODE
        from paper_api.highrisksession import HIGH_RISK_LABEL

        # Imported here, as in every other ``from_*`` above: the timestamp helper
        # belongs to the market-data layer, and this transport reads candles through
        # it rather than assuming the engine's datetimes are already UTC-aware.
        from .marketdata import as_utc

        state = session.high_risk_state()

        position = state.open_position
        signal = state.last_signal

        return cls(
            mode=HIGH_RISK_MODE,
            label=HIGH_RISK_LABEL,
            available=True,
            risk_fraction=state.risk_fraction,
            max_risk_fraction=state.max_risk_fraction,
            paper_cash=state.paper_cash,
            starting_balance=state.starting_balance,
            realized_pnl=state.realized_pnl,
            trade_count=state.trade_count,
            open_position=(
                PositionResponse(
                    side=position.side,
                    entry_time=as_utc(position.entry_time),
                    entry_price=position.entry_price,
                    quantity=position.quantity,
                    reason=position.reason,
                    raw_entry_price=position.raw_entry_price,
                    signal_close=position.signal_close,
                    trend_state=position.trend_state,
                    breakout_distance=position.breakout_distance,
                    retest_distance=position.retest_distance,
                    realised_volatility=position.realised_volatility,
                    mean_range=position.mean_range,
                    support_at_entry=position.support_at_entry,
                    resistance_at_entry=position.resistance_at_entry,
                )
                if position is not None
                else None
            ),
            exposure=state.exposure,
            exposure_fraction=state.exposure_fraction,
            position_count=state.position_count,
            max_positions=state.max_positions,
            exit_counts=dict(state.exit_counts),
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
            inherits_note=state.inherits_note,
            note=HIGH_RISK_NOTE,
            caution=state.caution,
            replay=ReplayStateResponse.from_state(state.replay, mode=HIGH_RISK_MODE),
        )
