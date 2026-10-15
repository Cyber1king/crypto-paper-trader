"""Market-specific cost profiles.

The engine carried one set of cost numbers and no notion of which market they
described. Adding a currency pair would therefore have costed it with crypto's
``spread_rate=0.0`` -- a cost-free market no venue has ever offered.

These tests pin the replacement: crypto's assumptions stay exactly as they were,
and every other market is refused with a reason instead of defaulted into.
"""
from __future__ import annotations

import pytest

from crypto_paper_lab.costs import (
    COST_DEDUCTION,
    DEFAULT_MARKET_TYPE,
    FILL_PRICE,
    MARKET_COST_BLOCKED,
    MARKET_COST_PROFILES,
    MarketCostProfile,
    TradingCosts,
    UnsupportedMarketCostProfile,
    costs_for_market,
    market_cost_profile,
    market_cost_report,
)


# 1. crypto defaults are untouched
def test_crypto_defaults_are_exactly_as_recorded():
    costs = TradingCosts()
    assert costs.fee_rate == 0.001
    assert costs.slippage_rate == 0.0005
    assert costs.spread_rate == 0.0
    assert costs.execution_model == COST_DEDUCTION
    assert costs.market_type == "crypto_spot"


def test_the_crypto_profile_reproduces_those_defaults_exactly():
    costs = costs_for_market("crypto_spot")
    assert costs.fee_rate == 0.001
    assert costs.slippage_rate == 0.0005
    assert costs.spread_rate == 0.0
    assert costs.execution_model == COST_DEDUCTION
    assert costs.market_type == "crypto_spot"


def test_the_default_market_type_is_crypto_spot():
    assert DEFAULT_MARKET_TYPE == "crypto_spot"


def test_positional_construction_still_works():
    """Existing call sites pass fee and slippage positionally."""

    costs = TradingCosts(0, 0)
    assert costs.fee_rate == 0.0
    assert costs.slippage_rate == 0.0
    assert costs.market_type == "crypto_spot"


# 2. forex is blocked, with a reason
@pytest.mark.parametrize("market", sorted(MARKET_COST_BLOCKED))
def test_blocked_markets_are_refused(market: str):
    with pytest.raises(UnsupportedMarketCostProfile):
        market_cost_profile(market)
    with pytest.raises(UnsupportedMarketCostProfile):
        costs_for_market(market)


def test_forex_spot_is_blocked_with_an_explanation():
    with pytest.raises(UnsupportedMarketCostProfile) as exc:
        costs_for_market("forex_spot")
    message = str(exc.value).lower()
    assert "forex_spot" in message
    assert "spread" in message


def test_forex_reference_rates_are_blocked_with_an_explanation():
    with pytest.raises(UnsupportedMarketCostProfile) as exc:
        costs_for_market("forex_reference_rates")
    assert "fabricated" in str(exc.value).lower()


def test_the_block_reason_names_what_is_missing_not_just_that_it_is():
    for market, reason in MARKET_COST_BLOCKED.items():
        assert len(reason) > 40, f"{market} needs an explanatory reason"


# 3. no default-based bypass
@pytest.mark.parametrize(
    "market", ["", "  ", "crypto", "Crypto_Spot", "crypto_spot_v2", "unknown", "none"]
)
def test_unknown_markets_are_refused_rather_than_defaulted(market: str):
    """A near-miss must not inherit crypto's numbers.

    This is the specific bypass the guard exists to close: a typo that silently
    resolved to a default would mis-cost a market without any error surfacing.
    """

    with pytest.raises(UnsupportedMarketCostProfile):
        costs_for_market(market)


def test_unknown_markets_are_refused_even_on_direct_construction():
    with pytest.raises(UnsupportedMarketCostProfile):
        TradingCosts(market_type="forex_something")


def test_direct_construction_cannot_bind_costs_to_an_unsupported_market():
    for market in ("forex_spot", "forex_reference_rates", "crypto_futures"):
        with pytest.raises(UnsupportedMarketCostProfile):
            TradingCosts(fee_rate=0.0001, market_type=market)


def test_no_forex_profile_exists_to_be_looked_up():
    assert "forex_spot" not in MARKET_COST_PROFILES
    assert "forex_reference_rates" not in MARKET_COST_PROFILES


def test_every_implemented_profile_is_crypto_spot():
    assert set(MARKET_COST_PROFILES) == {"crypto_spot"}


# 4. provenance is recorded, not implied
def test_the_zero_crypto_spread_is_labelled_an_assumption():
    profile = market_cost_profile("crypto_spot")
    assert profile.spread_rate == 0.0
    assert profile.provenance == "registered_assumption"
    assert "not a measured" in profile.rationale.lower()


def test_the_report_records_provenance_and_rationale():
    report = market_cost_report()
    entry = report["implemented"]["crypto_spot"]
    assert entry["spread_rate"] == 0.0
    assert entry["provenance"] == "registered_assumption"
    assert entry["rationale"]


def test_the_report_lists_blocked_markets_with_reasons():
    report = market_cost_report()
    assert "forex_spot" in report["blocked"]
    assert report["blocked"]["forex_spot"]


def test_the_report_is_deterministic():
    assert market_cost_report() == market_cost_report()


def test_a_profile_cannot_be_silently_retyped():
    profile = market_cost_profile("crypto_spot")
    with pytest.raises(Exception):
        profile.market_type = "forex_spot"  # type: ignore[misc]


# 5. overrides do not change the market
def test_explicit_overrides_are_preserved_for_diagnostics():
    costs = costs_for_market("crypto_spot", fee_rate=0.0, slippage_rate=0.0)
    assert costs.fee_rate == 0.0
    assert costs.slippage_rate == 0.0
    assert costs.market_type == "crypto_spot"


def test_an_override_cannot_rebind_costs_to_another_market():
    with pytest.raises(UnsupportedMarketCostProfile, match="cannot be overridden"):
        market_cost_profile("crypto_spot").to_trading_costs(
            market_type="forex_spot"
        )


def test_asking_for_forex_directly_is_refused_not_relabelled():
    with pytest.raises(UnsupportedMarketCostProfile):
        costs_for_market(market_type="forex_spot")


def test_a_fill_price_override_still_carries_the_market():
    costs = costs_for_market(
        "crypto_spot", spread_rate=0.0002, execution_model=FILL_PRICE
    )
    assert costs.execution_model == FILL_PRICE
    assert costs.market_type == "crypto_spot"


# 6. pre-existing cost rules still hold
def test_negative_rates_are_still_rejected():
    for kwargs in (
        {"fee_rate": -0.1},
        {"slippage_rate": -0.1},
        {"spread_rate": -0.1},
    ):
        with pytest.raises(ValueError):
            TradingCosts(**kwargs)


def test_spread_under_cost_deduction_is_still_rejected():
    with pytest.raises(ValueError, match="fill_price"):
        TradingCosts(spread_rate=0.0002, execution_model=COST_DEDUCTION)


def test_unknown_execution_model_is_still_rejected():
    with pytest.raises(ValueError, match="execution_model"):
        TradingCosts(execution_model="magic")


def test_adverse_rate_is_unchanged_for_crypto():
    assert TradingCosts().adverse_rate == 0.0005


def test_frozen_is_still_frozen():
    costs = TradingCosts()
    with pytest.raises(Exception):
        costs.fee_rate = 0.5  # type: ignore[misc]


# 7. profiles agree with the costs they build
def test_a_profile_round_trips_through_costs():
    profile = market_cost_profile("crypto_spot")
    costs = profile.to_trading_costs()
    assert costs.fee_rate == profile.fee_rate
    assert costs.slippage_rate == profile.slippage_rate
    assert costs.spread_rate == profile.spread_rate
    assert costs.execution_model == profile.execution_model
    assert costs.market_type == profile.market_type


def test_equal_costs_from_two_paths_are_equal():
    assert costs_for_market("crypto_spot") == TradingCosts()


def test_market_type_participates_in_the_frozen_cost_identity():
    """``costs_hash`` hashes the whole dataclass, so the market must be a field.

    If it were excluded, two cost sets differing only by market would hash
    alike and a research record could not tell them apart.
    """

    from dataclasses import fields

    names = {f.name for f in fields(TradingCosts)}
    assert "market_type" in names

# 8. agreement with the registry schema
def test_cost_and_registry_schema_agree_on_supported_markets():
    """Two independent lists of allowed markets will drift unless pinned."""

    from crypto_paper_lab.registry_schema import (
        MARKET_TYPES_BLOCKED as REGISTRY_BLOCKED,
    )
    from crypto_paper_lab.registry_schema import (
        MARKET_TYPES_SUPPORTED as REGISTRY_SUPPORTED,
    )

    assert set(MARKET_COST_PROFILES) == set(REGISTRY_SUPPORTED)


def test_cost_and_registry_schema_agree_on_blocked_markets():
    from crypto_paper_lab.registry_schema import (
        MARKET_TYPES_BLOCKED as REGISTRY_BLOCKED,
    )

    assert set(MARKET_COST_BLOCKED) == set(REGISTRY_BLOCKED)


def test_no_market_is_both_supported_and_blocked():
    assert not (set(MARKET_COST_PROFILES) & set(MARKET_COST_BLOCKED))
