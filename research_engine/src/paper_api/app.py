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

from crypto_paper_lab.walkforward import config_hash

from . import marketdata, perfstats, signals
from .config import ApiConfig, config_from_env, SERVICE_NAME
from .schemas import (
    AccountResponse,
    CandleModel,
    CostTotalsModel,
    ExecutionIdentityModel,
    MarketMetadataModel,
    MarketResponse,
    OpenPositionResponse,
    PositionResponse,
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


def create_app(
    config: ApiConfig | None = None,
    session: PaperSession | None = None,
) -> FastAPI:
    """Build the application.

    ``config`` and ``session`` are injectable so tests can construct the app
    without reading the ambient environment or minting a session id.
    """

    resolved = config or config_from_env()
    paper_session = session or PaperSession(service=SERVICE_NAME)

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

    return app


#: Module-level instance for ``uvicorn paper_api.app:app``.
app = create_app()