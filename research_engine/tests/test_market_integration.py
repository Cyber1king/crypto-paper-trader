"""Phase 75/76 integration: market identity across cost, dataset and report layers.

The three guards that existed before these phases each checked one thing -- the
cost names a market, the dataset names a market, the registry blocks the rest --
and none of them connected. These tests hold the connections closed.
"""
from __future__ import annotations

import pytest

from crypto_paper_lab.costs import (
    COST_DEDUCTION,
    DEFAULT_MARKET_TYPE,
    FILL_PRICE,
    MARKET_COST_BLOCKED,
    MARKET_COST_PROFILES,
    MarketCostMismatch,
    TradingCosts,
    UnsupportedMarketCostProfile,
    assert_costs_match_market,
    costs_for_market,
    market_cost_profile,
)
from crypto_paper_lab.dataset_identity import MARKET_TYPES_SUPPORTED as IDENTITY_SUPPORTED
from crypto_paper_lab.registry_schema import MARKET_TYPES_BLOCKED as SCHEMA_BLOCKED
from crypto_paper_lab.registry_schema import MARKET_TYPES_SUPPORTED as SCHEMA_SUPPORTED
from crypto_paper_lab.researchguard import MARKET_TYPES_SUPPORTED as GUARD_SUPPORTED
from crypto_paper_lab.walkforward import costs_hash, phase13_costs


# 1. one authority for "supported markets"
def test_every_module_agrees_on_supported_markets():
    assert set(MARKET_COST_PROFILES) == set(SCHEMA_SUPPORTED)
    assert set(MARKET_COST_PROFILES) == set(IDENTITY_SUPPORTED)
    assert set(MARKET_COST_PROFILES) == set(GUARD_SUPPORTED)


def test_every_module_agrees_on_blocked_markets():
    assert set(MARKET_COST_BLOCKED) == set(SCHEMA_BLOCKED)


def test_the_default_market_is_one_of_the_supported_markets():
    assert DEFAULT_MARKET_TYPE in set(MARKET_COST_PROFILES)


# 2. safe crypto compatibility
def test_the_frozen_costs_are_unchanged_and_still_cost_crypto():
    costs = phase13_costs()
    assert (costs.fee_rate, costs.slippage_rate, costs.spread_rate) == (
        0.001,
        0.0005,
        0.0,
    )
    assert costs.execution_model == COST_DEDUCTION
    assert costs.market_type == "crypto_spot"


def test_the_frozen_cost_hash_is_stable():
    """Guards against the record drifting while the numbers look the same."""

    assert costs_hash(phase13_costs()) == (
        "00E4C602B0C63601C742E15FDC685CF4FFA02CA2767F59F8CCFF2C30B576E69C"
    )


def test_building_costs_the_old_way_still_works():
    """No caller has to adopt the new API to keep working."""

    assert TradingCosts().market_type == DEFAULT_MARKET_TYPE
    assert TradingCosts(0, 0) == TradingCosts(fee_rate=0, slippage_rate=0)


# 3. invalid market identifiers fail closed
@pytest.mark.parametrize("market", sorted(MARKET_COST_BLOCKED))
def test_blocked_markets_cannot_be_constructed(market: str):
    with pytest.raises(UnsupportedMarketCostProfile):
        costs_for_market(market)
    with pytest.raises(UnsupportedMarketCostProfile):
        TradingCosts(market_type=market)


@pytest.mark.parametrize(
    "market", ["", "crypto", "CRYPTO_SPOT", "crypto_spot ", "crypto/spot", "eth"]
)
def test_unknown_market_identifiers_fail_closed(market: str):
    with pytest.raises(UnsupportedMarketCostProfile):
        costs_for_market(market)


def test_no_profile_can_be_invented_at_runtime():
    """A caller cannot add a profile and thereby authorise a market.

    The registry used to be a plain dict, so ``MARKET_COST_PROFILES["forex_spot"]
    = ...`` would have inserted a profile and opened a market the design
    deliberately blocks. It is now read-only.
    """

    with pytest.raises(TypeError):
        MARKET_COST_PROFILES["forex_spot"] = market_cost_profile("crypto_spot")


def test_the_profile_registry_cannot_be_cleared():
    with pytest.raises((AttributeError, TypeError)):
        MARKET_COST_PROFILES.clear()


# 4. configuration conflicts
def test_a_profile_cannot_be_relabelled_to_another_market():
    with pytest.raises(UnsupportedMarketCostProfile):
        market_cost_profile("crypto_spot").to_trading_costs(
            market_type="forex_spot"
        )


def test_mismatched_dataset_and_cost_markets_are_refused():
    """Only one market is implemented, so the mismatch path is exercised with
    a stand-in cost record rather than by inventing a second market."""

    class ForeignCosts:
        market_type = "crypto_perpetual"

    with pytest.raises(MarketCostMismatch, match="crypto_perpetual"):
        assert_costs_match_market(ForeignCosts(), "crypto_spot")


def test_a_declared_market_that_is_also_unimplemented_says_so():
    with pytest.raises(MarketCostMismatch) as exc:
        assert_costs_match_market(costs_for_market("crypto_spot"), "forex_spot")
    assert "not an implemented market" in str(exc.value)


def test_matching_markets_pass():
    assert_costs_match_market(costs_for_market("crypto_spot"), "crypto_spot")
    assert_costs_match_market(phase13_costs(), "crypto_spot")


# 5. double counting stays impossible
def test_spread_under_cost_deduction_is_still_refused():
    with pytest.raises(ValueError, match="fill_price"):
        costs_for_market("crypto_spot", spread_rate=0.0002)


def test_fee_and_slippage_are_not_confused_with_spread():
    costs = costs_for_market("crypto_spot")
    assert costs.spread_rate == 0.0
    assert costs.adverse_rate == costs.slippage_rate


def test_fill_price_may_charge_spread_and_slippage_together():
    costs = costs_for_market(
        "crypto_spot", spread_rate=0.0002, execution_model=FILL_PRICE
    )
    assert costs.adverse_rate == pytest.approx(0.0002 + 0.0005)


# 6. provenance is recorded where costs are reported
def test_the_reported_execution_identity_names_its_market():
    from crypto_paper_lab.replay import ExecutionIdentity

    identity = ExecutionIdentity.from_costs(phase13_costs(), 0.01)
    assert identity.market_type == "crypto_spot"
    assert identity.spread_rate == 0.0


def test_the_paper_api_execution_identity_names_its_market():
    from paper_api.session import ExecutionIdentity as ApiExecutionIdentity

    identity = ApiExecutionIdentity.from_costs(phase13_costs(), 0.01)
    assert identity.market_type == "crypto_spot"


def test_both_execution_identities_carry_the_same_fields():
    """The two parallel classes must not drift again.

    They were duplicated, and the duplication already caused a field to be
    dropped on the API path. If they diverge, one of them is wrong.
    """

    import dataclasses

    from crypto_paper_lab.replay import ExecutionIdentity as EngineIdentity
    from paper_api.session import ExecutionIdentity as ApiExecutionIdentity

    engine = {f.name for f in dataclasses.fields(EngineIdentity)}
    api = {f.name for f in dataclasses.fields(ApiExecutionIdentity)}
    assert engine == api


def test_the_api_schema_requires_the_market():
    from paper_api.schemas import ExecutionIdentityModel

    fields = ExecutionIdentityModel.model_fields
    assert "market_type" in fields
    assert fields["market_type"].is_required()


def test_the_zero_spread_remains_labelled_an_assumption():
    profile = market_cost_profile("crypto_spot")
    assert profile.provenance == "registered_assumption"
    assert "not a measured" in profile.rationale.lower()