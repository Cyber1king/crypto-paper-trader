"""FastAPI application factory for the local paper-trading API.

Phase 16A implements exactly one route: ``GET /healthz``, a liveness probe
returning a fixed payload.

Phase 16B adds ``GET /api/session``, a read-only projection of the
authoritative :class:`~paper_api.session.PaperSession`.

Phase 16C adds ``GET /api/market``, a read-only slice of the frozen research
dataset served through the engine's own loader.

Phase 16D adds ``GET /api/signal``, a read-only signal straight from
``crypto_paper_lab.strategy.analyze``.

Phase 16E adds ``GET /api/account``, ``GET /api/position`` and
``GET /api/trades``, all read-only serialisations of ``PaperBroker`` state.

Phase 16F adds ``GET /api/statistics``, a read-only closed-trade summary
delegated to ``crypto_paper_lab.stats``.

Design constraints applied here, and why:

* **No CORS middleware at all.** Adding none is stricter than adding a
  restricted policy, and it satisfies the "no wildcard" requirement by
  construction: a browser on another origin cannot read any response.
* **Interactive docs disabled.** A localhost research service does not need
  Swagger UI, and disabling it shrinks the surface. Re-enable deliberately if
  it is ever wanted.
* **No trading routes.** Not market data, not signals, not positions, not
  trades, not replay. Those belong to later phases and each will be added with
  its own tests.
* **No persistence and no engine accounting.** ``/api/session`` *reads* engine
  state through :class:`~paper_api.session.PaperSession`; it computes no
  balance, no P&L and no position of its own.

**Paper trading only.** No exchange connectivity, no order submission, no
wallet, no credentials.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query

from crypto_paper_lab.replay import (
    MAX_INTERVAL_MS,
    MIN_INTERVAL_MS,
    STATE_FINISHED,
)
from crypto_paper_lab.walkforward import config_hash

from . import marketdata, perfstats, signals
from .config import ApiConfig, config_from_env, SERVICE_NAME
from .replaysession import ReplaySession
from .schemas import (
    AccountResponse,
    CandleModel,
    CostTotalsModel,
    ExecutionIdentityModel,
    MarketMetadataModel,
    MarketResponse,
    OpenPositionResponse,
    PositionResponse,
    ReplayStateResponse,
    SessionResponse,
    SignalResponse,
    SignalSourceModel,
    SignalStrategyModel,
    StatisticsResponse,
    StrategyIdentityModel,
    TradeResponse,
    TradesResponse,
)
from .session import PaperSession

#: Returned verbatim by ``/healthz``. A module-level constant rather than a
#: computed value so the response bytes are identical on every call and across
#: every process - no timestamps, versions, hostnames or counters.
HEALTH_RESPONSE: dict[str, str] = {
    "status": "ok",
    "service": "crypto-paper-lab",
}

#: Upper bound on a single ``/api/replay/step`` batch. Matches Phase 17A §4.2.
#: A batch is N calls to the engine's own step, so this bounds work per request
#: rather than changing behaviour.
MAX_STEP_COUNT = 5000


def create_app(
    config: ApiConfig | None = None,
    session: PaperSession | None = None,
    replay: ReplaySession | None = None,
) -> FastAPI:
    """Build the application.

    ``config``, ``session`` and ``replay`` are injectable so tests can construct
    the app without reading the ambient environment, minting a session id, or
    loading the dataset.

    ``session`` and ``replay`` are two *views* of one authoritative broker. When
    a replay is supplied but no session, the session is derived from the replay's
    broker so ``/api/account`` and ``/api/replay`` can never describe different
    money. When neither is supplied, the original Phase 16 behaviour applies: a
    standalone session, with no replay involved.
    """

    resolved = config or config_from_env()
    replay_view = replay if replay is not None else ReplaySession()
    # One session object, rebound in place by ReplaySession when a reset installs
    # a new broker. The Phase 16 routes close over this exact object, so rebinding
    # rather than replacing is what keeps their account view current.
    paper_session = session or replay_view.session

    app = FastAPI(
        title="Crypto Paper Lab API",
        version="0.1.0",
        summary="Local paper-trading research API (no real trading).",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Exposed for logging and for tests. Holds no secrets.
    app.state.config = resolved
    app.state.session = paper_session
    app.state.replay = replay_view

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        """Liveness probe.

        Returns a fixed payload. It reports only that the process is up; it
        makes no claim about a dataset, engine state or trading readiness,
        because Phase 16A has no engine session to report on.
        """

        # A fresh dict per call so a caller cannot mutate the shared constant.
        return dict(HEALTH_RESPONSE)

    @app.get("/api/session", response_model=SessionResponse, tags=["session"])
    def session_state() -> SessionResponse:
        """Read-only snapshot of the paper session.

        Every figure is read from the research engine; nothing is recomputed
        here. No balance, position or P&L is calculated inside the API layer.
        """

        return SessionResponse.from_view(paper_session.view)

    @app.get("/api/market", response_model=MarketResponse, tags=["market"])
    def market_candles(
        start: datetime | None = Query(
            default=None,
            description=(
                "Inclusive lower bound on bar time. Accepts a naive "
                "timestamp, which is read as UTC, or an offset-aware one, "
                "which is converted to UTC."
            ),
        ),
        end: datetime | None = Query(
            default=None,
            description="Inclusive upper bound on bar time. Same rules as start.",
        ),
        limit: int = Query(
            default=marketdata.DEFAULT_LIMIT,
            ge=1,
            le=marketdata.MAX_LIMIT,
            description=(
                f"Maximum candles to return, 1-{marketdata.MAX_LIMIT}. When "
                "more candles match, the most recent slice is returned."
            ),
        ),
    ) -> MarketResponse:
        """Historical OHLCV candles from the frozen research dataset.

        Read-only. Nothing is downloaded, interpolated or synthesised, and no
        filesystem path is disclosed. With no dates supplied the response is a
        bounded recent slice, never the whole series.
        """

        if (
            start is not None
            and end is not None
            and marketdata.as_naive_utc(start) > marketdata.as_naive_utc(end)
        ):
            raise HTTPException(
                status_code=422,
                detail="start must be earlier than or equal to end",
            )

        candles = marketdata.load_research_candles()
        selected, truncated = marketdata.select_candles(
            candles, start, end, limit
        )

        config = paper_session.config

        return MarketResponse(
            metadata=MarketMetadataModel(
                asset=config.asset,
                timeframe=config.timeframe,
                source=marketdata.SOURCE_LABEL,
                dataset_sha256=marketdata.dataset_identity(),
                dataset_candles=len(candles),
                dataset_first_timestamp=marketdata.as_utc(candles[0].timestamp),
                dataset_last_timestamp=marketdata.as_utc(candles[-1].timestamp),
                returned_candles=len(selected),
                truncated=truncated,
                start=marketdata.as_utc(start) if start is not None else None,
                end=marketdata.as_utc(end) if end is not None else None,
                limit=limit,
            ),
            candles=[
                CandleModel(
                    timestamp=marketdata.as_utc(candle.timestamp),
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
                for candle in selected
            ],
        )

    @app.get("/api/signal", response_model=SignalResponse, tags=["signal"])
    def current_signal(
        at: datetime | None = Query(
            default=None,
            description=(
                "Optional exact bar time. Must match a candle in the dataset "
                "precisely; a near miss is a 404, never an interpolation. "
                "Omit it for the latest completed candle."
            ),
        ),
    ) -> SignalResponse:
        """The existing strategy's signal for a chosen candle.

        Read-only research output. No execution, no fill, no position and no
        order. Every trading value comes from the engine's ``Signal``; the API
        reimplements no part of the strategy.
        """

        config = paper_session.config
        candles = marketdata.load_research_candles()

        try:
            signal = signals.resolve_signal(
                candles,
                config,
                at=at,
                index_of=marketdata.candle_index_by_timestamp(),
            )
        except signals.UnknownTimestampError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except signals.InsufficientHistoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return SignalResponse(
            service=paper_session.view.service,
            asset=config.asset,
            timeframe=config.timeframe,
            timestamp=marketdata.as_utc(signal.timestamp),
            signal=signal.side,
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
            strategy=SignalStrategyModel(
                config_hash=config_hash(config),
                config_repr=repr(config),
            ),
            source=SignalSourceModel(
                dataset_sha256=marketdata.dataset_identity(),
                dataset_first_timestamp=marketdata.as_utc(
                    candles[0].timestamp
                ),
                dataset_last_timestamp=marketdata.as_utc(
                    candles[-1].timestamp
                ),
            ),
        )

    @app.get("/api/account", response_model=AccountResponse, tags=["account"])
    def account_state() -> AccountResponse:
        """Paper account figures, read from ``PaperBroker``.

        No arithmetic here beyond the engine's own
        ``balance - starting_balance``. No available balance, reserved
        capital, equity or unrealized P&L is reported, because the engine
        represents none of them.
        """

        state = paper_session.account

        return AccountResponse(
            starting_balance=state.starting_balance,
            balance=state.balance,
            realized_pnl=state.realized_pnl,
            trade_count=state.trade_count,
        )

    @app.get(
        "/api/position", response_model=OpenPositionResponse, tags=["position"]
    )
    def open_position() -> OpenPositionResponse:
        """The open position, if any.

        No mark price and no unrealized P&L: the engine has no live price
        feed, so any current valuation here would be invented. Cost fields
        are omitted because the broker computes them only at close.
        """

        state = paper_session.position

        if state is None:
            return OpenPositionResponse(has_position=False, position=None)

        return OpenPositionResponse(
            has_position=True,
            position=PositionResponse(
                side=state.side,
                entry_time=marketdata.as_utc(state.entry_time),
                entry_price=state.entry_price,
                quantity=state.quantity,
                reason=state.reason,
                raw_entry_price=state.raw_entry_price,
                signal_close=state.signal_close,
                trend_state=state.trend_state,
                breakout_distance=state.breakout_distance,
                retest_distance=state.retest_distance,
                realised_volatility=state.realised_volatility,
                mean_range=state.mean_range,
                support_at_entry=state.support_at_entry,
                resistance_at_entry=state.resistance_at_entry,
            ),
        )

    @app.get("/api/trades", response_model=TradesResponse, tags=["trades"])
    def trade_history() -> TradesResponse:
        """The closed-trade journal, in the broker's own append order.

        Serialised verbatim: ``pnl``, ``net_pnl`` and ``total_friction`` are
        the engine's own properties, not recomputed. No pagination is
        invented for a journal this size, and no trade is ever fabricated.
        """

        trades = [
            TradeResponse(
                side=trade.side,
                entry_time=marketdata.as_utc(trade.entry_time),
                exit_time=(
                    marketdata.as_utc(trade.exit_time)
                    if trade.exit_time is not None
                    else None
                ),
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                reason=trade.reason,
                exit_reason=trade.exit_reason,
                bars_held=trade.bars_held,
                raw_entry_price=trade.raw_entry_price,
                raw_exit_price=trade.raw_exit_price,
                costs=trade.costs,
                fee_total=trade.fee_total,
                slippage_total=trade.slippage_total,
                spread_total=trade.spread_total,
                pnl=trade.pnl,
                net_pnl=trade.net_pnl,
                total_friction=trade.total_friction,
                signal_close=trade.signal_close,
                trend_state=trade.trend_state,
                breakout_distance=trade.breakout_distance,
                retest_distance=trade.retest_distance,
                realised_volatility=trade.realised_volatility,
                mean_range=trade.mean_range,
                support_at_entry=trade.support_at_entry,
                resistance_at_entry=trade.resistance_at_entry,
            )
            for trade in paper_session.trades
        ]

        return TradesResponse(
            trades=trades, trade_count=len(trades)
        )

    @app.get(
        "/api/statistics", response_model=StatisticsResponse, tags=["statistics"]
    )
    def performance_statistics() -> StatisticsResponse:
        """Closed-trade performance statistics.

        Every figure comes from ``crypto_paper_lab.stats.performance`` and
        ``stats.cost_breakdown`` via :mod:`paper_api.perfstats`. The route
        copies values; it computes none.

        Because no replay engine runs, the journal of a live server is empty
        and these numbers are correspondingly degenerate. That is the honest
        state, not a fault: there is nothing to summarise yet.
        """

        view = paper_session.view
        summary = perfstats.summarise(
            paper_session.trades,
            # The broker's own starting balance, not a constant declared here.
            view.account.starting_balance,
        )

        return StatisticsResponse(
            service=view.service,
            basis=summary.basis,
            trades=summary.trades,
            net_pnl=summary.net_pnl,
            win_rate=summary.win_rate,
            profit_factor=summary.profit_factor,
            profit_factor_infinite=summary.profit_factor_infinite,
            average_pnl=summary.average_pnl,
            max_drawdown=summary.max_drawdown,
            ending_balance=summary.ending_balance,
            costs=CostTotalsModel(**vars(summary.costs)),
            strategy=StrategyIdentityModel(**vars(view.strategy)),
            execution=ExecutionIdentityModel(**vars(view.execution)),
        )

    # -----------------------------------------------------------------------
    # replay (Phase 17D)
    #
    # Each handler below is a projection. It calls one method on ReplaySession,
    # which calls one method on Replay, and returns the state the engine produced.
    # There is no lifecycle logic, no step algorithm and no trading arithmetic in
    # this section - that duplication is the failure mode the whole architecture
    # exists to prevent.
    # -----------------------------------------------------------------------

    @app.get("/api/replay", response_model=ReplayStateResponse, tags=["replay"])
    def replay_state() -> ReplayStateResponse:
        """Authoritative replay state, read from ``Replay.state``."""

        return ReplayStateResponse.from_state(replay_view.snapshot())

    @app.post(
        "/api/replay/start", response_model=ReplayStateResponse, tags=["replay"]
    )
    def replay_start(
        interval_ms: int | None = Query(
            default=None,
            description=(
                "Auto-run pace in milliseconds, "
                f"{MIN_INTERVAL_MS}-{MAX_INTERVAL_MS}. Omit to keep the current "
                "interval. Out of range is rejected, never clamped."
            ),
        ),
    ) -> ReplayStateResponse:
        """Arm auto-run. Delegates to ``Replay.start()`` unchanged.

        A finished replay stays finished and unarmed, per the Phase 17C
        transition table. Phase 17A section 21 still requires the transport to
        report that as ``409 REPLAY_FINISHED``, so the refusal lives here rather
        than in the engine - which is what lets both documents hold at once.
        """

        if replay_view.snapshot().status == STATE_FINISHED:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "REPLAY_FINISHED",
                    "message": (
                        "replay has reached the end of the dataset; reset it "
                        "before starting again"
                    ),
                },
            )

        return ReplayStateResponse.from_state(replay_view.start(interval_ms))

    @app.post(
        "/api/replay/pause", response_model=ReplayStateResponse, tags=["replay"]
    )
    def replay_pause() -> ReplayStateResponse:
        """Disarm auto-run. Delegates to ``Replay.pause()`` unchanged."""

        return ReplayStateResponse.from_state(replay_view.pause())

    @app.post(
        "/api/replay/step", response_model=ReplayStateResponse, tags=["replay"]
    )
    def replay_step(
        count: int = Query(
            default=1,
            ge=1,
            le=MAX_STEP_COUNT,
            description=(
                f"Bars to advance, 1-{MAX_STEP_COUNT}. Batching is deterministic "
                "because it is literally that many calls to the same method."
            ),
        ),
    ) -> ReplayStateResponse:
        """Advance the replay. Delegates to ``Replay.step()`` once per bar.

        A batch is a loop over the engine's own step, not a faster algorithm, so
        one ``count=40`` request and forty ``count=1`` requests leave the replay in
        identical state.

        The batch is **clamped to the bars that remain**, plus one step to let the
        replay reach its terminal state. Two facts about the engine make the
        ``+ 1`` necessary:

        * The engine applies end-of-data closure on the call *after* the last bar
          is consumed, so consuming every remaining bar leaves ``cursor`` at the
          end while the status is not yet ``finished``.
        * Without clamping, a 5000-bar request near the end would step until the
          data ran out, the engine would refuse the next step, and the request
          would answer 409 *after* having advanced the replay - telling the caller
          it had failed while holding state it was never shown.

        So a request that reaches or exceeds the end performs the final step and
        returns ``finished``. A request that stays within the data performs
        exactly the bars asked for.

        Stepping a replay that is already finished is still a refusal: the engine
        raises and the caller gets ``409 REPLAY_FINISHED``.
        """

        state = replay_view.snapshot()
        remaining = max(state.dataset.candle_count - state.cursor, 0)
        steps = count if count < remaining else remaining + 1

        for _ in range(steps):
            state = replay_view.step()

        return ReplayStateResponse.from_state(state)

    @app.post(
        "/api/replay/reset", response_model=ReplayStateResponse, tags=["replay"]
    )
    def replay_reset() -> ReplayStateResponse:
        """Rewind the replay. Delegates to ``Replay.reset()`` unchanged.

        Returns ``409 POSITION_OPEN`` when a paper position is open. The engine
        refuses rather than discarding the trade, and the API does not work around
        that refusal.
        """

        return ReplayStateResponse.from_state(replay_view.reset())

    return app


#: Module-level instance for ``uvicorn paper_api.app:app``.
app = create_app()