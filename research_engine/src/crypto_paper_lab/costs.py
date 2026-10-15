from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

#: Fills are recorded at the raw market price and fees plus slippage are
#: deducted from P&L afterwards. This is the legacy Phase 5-11 model and
#: remains the default so that every previously recorded research result
#: reproduces exactly.
COST_DEDUCTION = "cost_deduction"

#: Spread and slippage are applied to the fill price itself. The recorded
#: entry/exit prices are the prices actually paid or received.
FILL_PRICE = "fill_price"

#: The market this repository implements cost accounting for.
DEFAULT_MARKET_TYPE = "crypto_spot"

#: Markets blocked from cost accounting, with the reason.
#:
#: These are listed rather than left absent so that an unsupported market
#: produces an explanation instead of a bare ``KeyError``. The forex reasons
#: are not a formality: a spread that is not measured is not a spread, and
#: carrying crypto's ``0.0`` into a currency pair would report a cost-free
#: market that no venue has ever offered.
MARKET_COST_BLOCKED = {
    "forex_spot": (
        "No verified spread or fee schedule for FX spot. A currency pair's "
        "spread is quoted in pips and varies by venue, session and tier; "
        "carrying a crypto default would silently mis-cost every fill."
    ),
    "forex_reference_rates": (
        "Reference rates are mid-market quotes with no venue, no order book "
        "and no spread to charge. Any cost model here would be fabricated."
    ),
    "crypto_perpetual": (
        "Perpetual funding costs are periodic and do not reduce to a "
        "proportional per-fill rate."
    ),
    "crypto_futures": (
        "Futures carry basis, funding and expiry effects that a proportional "
        "per-fill model does not represent."
    ),
}


class UnsupportedMarketCostProfile(RuntimeError):
    """A market was asked for cost accounting that has not been implemented.

    A ``RuntimeError`` rather than ``ValueError`` because this is not a bad
    argument value -- it is the absence of a validated model, which is a
    condition of the system, not of the caller.
    """


@dataclass(frozen=True)
class MarketCostProfile:
    """A validated, market-specific cost model.

    Every profile carries its own provenance so that a reader of a research
    result can tell a measured figure from an assumed one. A profile whose
    provenance is an assumption says so in the record rather than leaving the
    reader to infer it from the absence of a citation.
    """

    market_type: str
    fee_rate: float
    slippage_rate: float
    spread_rate: float
    execution_model: str
    provenance: str
    rationale: str

    def to_trading_costs(self, **overrides: object) -> "TradingCosts":
        """Build costs for this market. Explicit overrides are preserved.

        Overrides exist for diagnostics -- a zero-cost run is a legitimate way
        to isolate model signal. They do not change which market the costs
        describe, so the profile's ``market_type`` is always carried through and
        attempting to override it is refused rather than resolved.
        """

        if "market_type" in overrides:
            raise UnsupportedMarketCostProfile(
                "market_type cannot be overridden: these costs describe "
                f"{self.market_type!r}, and relabelling them would make the "
                "rates belong to a market they were not measured for"
            )

        return TradingCosts(
            fee_rate=overrides.pop("fee_rate", self.fee_rate),  # type: ignore[arg-type]
            slippage_rate=overrides.pop(
                "slippage_rate", self.slippage_rate  # type: ignore[arg-type]
            ),
            spread_rate=overrides.pop(
                "spread_rate", self.spread_rate  # type: ignore[arg-type]
            ),
            execution_model=overrides.pop(  # type: ignore[arg-type]
                "execution_model", self.execution_model
            ),
            market_type=self.market_type,
            **overrides,  # type: ignore[arg-type]
        )


#: The only implemented profile. Everything else is refused.
#: Read-only. A plain dict here would let any caller insert a
#: profile at runtime and thereby authorise a market the design
#: deliberately blocks, turning a compile-time decision into a
#: runtime accident.
MARKET_COST_PROFILES: Mapping[str, MarketCostProfile] = MappingProxyType({
    "crypto_spot": MarketCostProfile(
        market_type="crypto_spot",
        fee_rate=0.001,
        slippage_rate=0.0005,
        spread_rate=0.0,
        execution_model=COST_DEDUCTION,
        provenance="registered_assumption",
        rationale=(
            "Phase 13 research record. Fee and slippage are documented "
            "assumptions. The spread is 0.0, which is an assumption of a "
            "cost-free fill, NOT a measured Binance spread -- it is not "
            "evidence that Binance quotes a zero spread, and results "
            "sensitive to it should be read accordingly."
        ),
    )
})


def market_cost_profile(market_type: str) -> MarketCostProfile:
    """Return the validated profile for ``market_type`` or refuse.

    Refusal is total: unknown market names are refused exactly as known
    unsupported ones are. Accepting an unrecognised name and falling back to a
    default is the specific bypass this exists to close.
    """

    if market_type in MARKET_COST_PROFILES:
        return MARKET_COST_PROFILES[market_type]

    if market_type in MARKET_COST_BLOCKED:
        raise UnsupportedMarketCostProfile(
            f"cost accounting is not implemented for {market_type!r}: "
            f"{MARKET_COST_BLOCKED[market_type]}"
        )

    raise UnsupportedMarketCostProfile(
        f"unknown market_type {market_type!r}; implemented markets are "
        f"{sorted(MARKET_COST_PROFILES)} and known-blocked markets are "
        f"{sorted(MARKET_COST_BLOCKED)}. No default is applied."
    )


def costs_for_market(market_type: str, **overrides: object) -> "TradingCosts":
    """Build :class:`TradingCosts` for a named market, or refuse."""

    return market_cost_profile(market_type).to_trading_costs(**overrides)


class MarketCostMismatch(RuntimeError):
    """A dataset declares one market; the costs in force describe another."""


def assert_costs_match_market(
    costs: "TradingCosts", declared_market_type: str
) -> None:
    """Refuse to evaluate a dataset under another market's cost model.

    Two separate guards already exist -- each cost object must name a market
    with a validated profile, and each dataset must declare a market the loader
    supports. Neither connects the two. Without this, a dataset declared as one
    market could be run with another market's rates, and every number produced
    would be quietly wrong rather than refused.

    The declared market is validated first, so an unsupported market is refused
    as unsupported rather than reported as a mismatch against a profile that
    was never valid for it.
    """

    if costs.market_type != declared_market_type:
        extra = (
            ""
            if declared_market_type in MARKET_COST_PROFILES
            else f" ({declared_market_type!r} is also not an implemented market)"
        )
        raise MarketCostMismatch(
            f"dataset declares market_type={declared_market_type!r} but the "
            f"costs in force describe {costs.market_type!r}{extra}; that spread "
            "and fee schedule were not measured for this market and applying "
            "them would mis-state every result"
        )

    market_cost_profile(declared_market_type)


def market_cost_report() -> dict:
    """Deterministic, serialisable description of what is and is not modelled."""

    return {
        "implemented": {
            name: {
                "fee_rate": profile.fee_rate,
                "slippage_rate": profile.slippage_rate,
                "spread_rate": profile.spread_rate,
                "execution_model": profile.execution_model,
                "provenance": profile.provenance,
                "rationale": profile.rationale,
            }
            for name, profile in sorted(MARKET_COST_PROFILES.items())
        },
        "blocked": dict(sorted(MARKET_COST_BLOCKED.items())),
        "default_market_type": DEFAULT_MARKET_TYPE,
    }


@dataclass(frozen=True)
class TradingCosts:
    """Configurable costs for paper-trading research.

    Parameters
    ----------
    fee_rate:
        Proportional trading fee charged once on each filled notional, so a
        round trip pays ``fee_rate`` twice in total.
    slippage_rate:
        Proportional adverse price movement applied to each leg. It models
        size and latency effects: you buy slightly above the reference and
        sell slightly below it.
    spread_rate:
        Proportional half-spread applied to each leg, kept separate from
        ``slippage_rate`` so that crossing the bid-ask spread can be
        reported independently of size/latency slippage. Requires
        ``execution_model="fill_price"``; under ``"cost_deduction"`` the
        spread is indistinguishable from slippage and charging both would
        double count, so it is rejected.
    execution_model:
        ``"cost_deduction"`` (default) keeps fills at the raw reference price
        and deducts fees plus slippage from P&L afterwards.
        ``"fill_price"`` applies spread and slippage to the fill price,
        derives position size from the real entry fill, and charges fees on
        filled notional.

    Notes
    -----
    Both models are deterministic and use no randomness.

    The two models are only *approximately* equivalent in P&L at matching
    rates; they are not mathematically identical. Two effects separate them.
    First, ``fill_price`` derives position size from the slipped entry fill
    rather than the raw reference price, so it holds marginally fewer units
    on a long and marginally more on a short. Second, it charges fees on the
    notional actually transacted rather than on the raw reference notional.
    For the default 0.05% slippage these effects are around 5e-4 relative,
    not negligible at the fourth decimal place, and they grow with the
    configured rates. Use one model consistently when comparing runs.
    """

    fee_rate: float = 0.001
    slippage_rate: float = 0.0005
    spread_rate: float = 0.0
    execution_model: Literal["cost_deduction", "fill_price"] = COST_DEDUCTION
    #: Which market these costs describe. Added so that no cost object can
    #: exist without claiming one -- the previous design let a currency pair
    #: be evaluated with no market named at all, inheriting crypto's numbers.
    market_type: str = DEFAULT_MARKET_TYPE

    def __post_init__(self) -> None:
        if self.fee_rate < 0:
            raise ValueError("fee_rate cannot be negative")

        if self.slippage_rate < 0:
            raise ValueError("slippage_rate cannot be negative")

        if self.spread_rate < 0:
            raise ValueError("spread_rate cannot be negative")

        if self.execution_model not in (COST_DEDUCTION, FILL_PRICE):
            raise ValueError(
                f"unknown execution_model: {self.execution_model!r}"
            )

        if self.spread_rate > 0 and self.execution_model == COST_DEDUCTION:
            raise ValueError(
                "spread_rate requires execution_model='fill_price'; under "
                "'cost_deduction' the spread cannot be separated from "
                "slippage and charging both would double count"
            )

        # Every cost object is bound to a market with a validated profile. An
        # unsupported market is refused here as well as in the factory, so the
        # guard holds for direct construction and not only the convenience
        # constructors.
        market_cost_profile(self.market_type)

    @property
    def adverse_rate(self) -> float:
        """Total proportional adverse move applied to each leg."""

        return self.spread_rate + self.slippage_rate
