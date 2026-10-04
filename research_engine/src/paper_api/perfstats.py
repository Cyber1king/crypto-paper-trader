"""Closed-trade performance statistics, delegated to the research engine.

Phase 16F. This module exists so ``app.py`` stays a pure serialiser. It calls
exactly two engine functions and derives every reported figure from their
return values:

``crypto_paper_lab.stats.performance``
    ``trades``, ``net_pnl``, ``win_rate``, ``profit_factor``, ``average_pnl``,
    ``max_drawdown``, ``ending_balance``.
``crypto_paper_lab.stats.cost_breakdown``
    ``fee_total``, ``spread_total``, ``slippage_total``, ``total_friction``,
    ``deducted_costs``.

Exactly one transformation is applied, and it is not optional:

``profit_factor`` when infinite
    ``stats.performance`` returns ``float("inf")`` whenever ``gross_loss == 0``.
    ``Infinity`` is **not valid JSON** - ``json.dumps`` will happily emit the
    bare token, which ``JSON.parse`` then rejects, breaking every consumer of
    an otherwise successful response. The integration plan's finding N1
    requires emitting ``{"profit_factor": null, "profit_factor_infinite": true}``
    instead. Substituting a large finite number would fabricate a statistic,
    so the flag travels with the value and the UI renders "∞ (no losing
    trades)".

Nothing else is touched. In particular ``max_drawdown`` is passed through as
the **fraction** the engine computed - it is not multiplied by 100 - and
``net_pnl``, ``average_pnl`` and ``win_rate`` are the engine's own values.

Deliberately absent, and why
---------------------------

* **No unrealized P&L or equity.** ``stats.performance`` is defined over closed
  trades; the broker credits cash only on close. A statistic mixing in an open
  position would need a mark price, and the session has no live price feed.
* **No mark-to-market drawdown.** It exists as
  ``robustness.mark_to_market_drawdown``, but it needs a candle array aligned
  to the journal. No replay consumes candles in Phase 16, so there is nothing to
  align to. Integration-plan open question 4 records it as omitted from the
  minimum; if it is ever added it must be labelled distinctly from the realized
  figure above, because the two differ by construction.
* **No ``sharpe``, ``sortino``, ``calmar`` or recovery factor.** The engine
  defines none. The API is not a place to introduce a risk metric the research
  record never validated.
* **No bootstrap confidence interval, no monthly breakdown, no concentration
  analysis.** ``robustness`` has all three and they are legitimate, but they
  belong to a later phase with its own contract. ``block_length`` in particular
  is a pre-declared research choice that must not become an opaque query
  parameter.
* **No pagination or date filtering.** The journal is the whole input, matching
  the plan's "computed from closed trades only".
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isinf
from typing import Sequence

from crypto_paper_lab import stats
from crypto_paper_lab.models import PaperTrade

__all__ = [
    "BASIS_CLOSED_TRADES",
    "UNSUPPORTED_METRICS",
    "CostTotals",
    "PerformanceSummary",
    "summarise",
]

#: What the numbers describe. Stated in the payload so a client cannot mistake
#: a closed-trade view for a live mark-to-market one.
BASIS_CLOSED_TRADES = "closed_trades"

#: Metrics deliberately not reported, with the reason. Kept beside the code
#: rather than only in prose so an omission reads as a decision.
UNSUPPORTED_METRICS: dict[str, str] = {
    "unrealized_pnl": "stats.performance is closed-trade only; the broker "
                      "credits cash on close and there is no mark price",
    "equity": "balance plus unrealized_pnl, which is unavailable",
    "mark_to_market_max_dd": "needs a candle array aligned to the journal; no "
                             "replay consumes candles in Phase 16",
    "sharpe_ratio": "the engine defines no risk-adjusted return measure",
    "sortino_ratio": "the engine defines no downside-deviation measure",
    "calmar_ratio": "no engine definition, and it would require the "
                    "mark-to-market drawdown that is unavailable",
    "recovery_factor": "requires an unrealized trough equity",
    "bootstrap_ci": "block_length is a pre-declared research choice; exposing "
                    "it as a query parameter would invite unfalsifiable use",
    "monthly_breakdown": "robustness.monthly_breakdown exists but belongs to a "
                         "later phase with its own contract",
    "concentration": "robustness.concentration_stats exists but belongs to a "
                     "later phase with its own contract",
}


@dataclass(frozen=True)
class CostTotals:
    """Aggregated execution costs, copied from ``stats.cost_breakdown``."""

    fee_total: float
    spread_total: float
    slippage_total: float
    total_friction: float
    deducted_costs: float


@dataclass(frozen=True)
class PerformanceSummary:
    """Headline performance, copied from ``stats.performance``."""

    basis: str
    trades: int
    net_pnl: float
    win_rate: float
    #: ``None`` when the engine reported infinity. Read ``profit_factor_infinite``
    #: rather than assuming ``None`` means "no data".
    profit_factor: float | None
    profit_factor_infinite: bool
    average_pnl: float
    #: A **fraction**, not a percentage. 0.0017 means 0.17%.
    max_drawdown: float
    ending_balance: float
    costs: CostTotals


def summarise(
    trades: Sequence[PaperTrade],
    starting_balance: float,
) -> PerformanceSummary:
    """Summarise a closed-trade journal through the engine's own statistics.

    ``trades`` should be the broker journal, which contains only closed trades;
    ``stats.performance`` additionally filters on ``net_pnl is not None`` so an
    unexpected entry cannot corrupt a total.

    Every value is cast to ``float``/``int`` because the engine returns ``int``
    zeros for empty aggregates (``sum([])`` is ``0``), which would otherwise
    serialise as ``0`` where a float is expected. That is a type normalisation,
    not a recalculation.
    """

    report = stats.performance(trades, starting_balance)
    breakdown = stats.cost_breakdown(trades)

    raw_profit_factor = float(report["profit_factor"])
    infinite = isinf(raw_profit_factor)

    return PerformanceSummary(
        basis=BASIS_CLOSED_TRADES,
        trades=int(report["trades"]),
        net_pnl=float(report["net_pnl"]),
        win_rate=float(report["win_rate"]),
        profit_factor=None if infinite else raw_profit_factor,
        profit_factor_infinite=infinite,
        average_pnl=float(report["average_pnl"]),
        max_drawdown=float(report["max_drawdown"]),
        ending_balance=float(report["ending_balance"]),
        costs=CostTotals(
            fee_total=float(breakdown["fee_total"]),
            spread_total=float(breakdown["spread_total"]),
            slippage_total=float(breakdown["slippage_total"]),
            total_friction=float(breakdown["total_friction"]),
            deducted_costs=float(breakdown["deducted_costs"]),
        ),
    )