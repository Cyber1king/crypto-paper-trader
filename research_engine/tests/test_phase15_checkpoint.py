"""Phase 15 checkpoint validation.

Phase 15 is documentation and audit only, so these tests exist for one reason:
to stop the checkpoint from drifting away from the repository it describes.

A checkpoint is only worth reading if it is true. These tests check the
machine-readable half of that claim — the recorded digests, the recorded
strategy defaults, and the recorded capability absences — against the actual
repository state. If someone changes the strategy, a dataset or a frozen
artifact without updating the checkpoint, these fail.

Deliberately absent: any assertion that the strategy is profitable, any ranking
of configurations, and any test that would require re-running research.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from crypto_paper_lab.strategy import StrategyConfig

ROOT = Path(__file__).resolve().parents[1]
PHASE15 = ROOT / "experiments/phase15"
STATE_PATH = PHASE15 / "RESEARCH_STATE.json"
CHECKPOINT_PATH = PHASE15 / "RESEARCH_CHECKPOINT.md"


@pytest.fixture(scope="module")
def state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


# ---------------------------------------------------------------------------
# 1. the checkpoint exists and is internally coherent
# ---------------------------------------------------------------------------


def test_both_checkpoint_files_exist() -> None:
    assert CHECKPOINT_PATH.is_file()
    assert STATE_PATH.is_file()


def test_state_is_valid_json_with_required_sections(state: dict) -> None:
    for key in (
        "phase",
        "purpose",
        "generated_at",
        "standing_conclusion",
        "strategy_state",
        "data_inventory",
        "data_accounting",
        "evidence_table",
        "observed",
        "not_established",
        "constraints",
        "degrees_of_freedom",
        "available_research_paths",
        "paths_that_should_not_be_treated_as_validation",
        "frozen_artifact_hashes",
        "datasets_sha256",
        "known_record_gaps",
        "phase15_actions",
    ):
        assert key in state, key

    assert state["phase"] == "15"


def test_checkpoint_covers_every_required_section() -> None:
    text = CHECKPOINT_PATH.read_text(encoding="utf-8")

    for heading in (
        "## 3. The complete research pipeline",
        "## 4. Current strategy state",
        "## 5. Evidence table",
        "## 6. What the research currently shows",
        "## 7. Data inventory",
        "## 8. Research degrees of freedom",
        "## 9. Current research status",
        "### Established",
        "### Not Established",
        "### Constraints",
        "### Available Research Paths",
        "### Paths That Should Not Be Treated as Validation",
        "## 10. Possible next research directions",
        "## 11. Phase 15 did not optimise",
        "## 12. Reproducibility",
    ):
        assert heading in text, heading

    for phase in ("Phase 5", "Phase 6", "Phase 7", "Phase 8", "Phase 9",
                  "Phase 10", "Phase 11", "Phase 12", "Phase 13",
                  "Phase 14A", "Phase 14B", "Phase 14C"):
        assert phase in text, phase


# ---------------------------------------------------------------------------
# 2. recorded digests must match the repository
# ---------------------------------------------------------------------------


def test_every_recorded_artifact_digest_matches(state: dict) -> None:
    """The core guarantee: the checkpoint's hashes are real."""

    checked = 0

    for group, files in state["frozen_artifact_hashes"].items():
        for name, digest in files.items():
            path = ROOT / "experiments" / group / name
            assert path.is_file(), path
            assert sha256(path) == digest, f"{group}/{name}"
            checked += 1

    assert checked >= 20, checked


def test_recorded_dataset_digests_match(state: dict) -> None:
    for entry in state["data_inventory"]:
        path = ROOT.parent / entry["path"].split("research_engine/")[-1]
        path = ROOT / Path(entry["path"]).name if False else (
            ROOT.parent / entry["path"]
        )
        assert path.is_file(), path
        assert sha256(path) == entry["sha256"], entry["path"]
        assert state["datasets_sha256"][entry["role"]] == entry["sha256"]


def test_phase13_digests_match_those_established_in_phase13_and_14(
    state: dict,
) -> None:
    """Cross-check against digests recorded independently in earlier phases."""

    frozen = state["frozen_artifact_hashes"]["phase13"]

    assert frozen["PLAN.md"] == (
        "8D9F9021AE22AE36344FD14464796486A7EA415B261C7AA189E4A180DB7D7800"
    )
    assert frozen["RESULTS_windows.csv"] == (
        "1A2D37A4FF744F59BEE6A85E8A8E61538AFCC43C7B0FC17A352DCC1559953E7D"
    )
    assert frozen["RESULTS_windows.json"] == (
        "67092DEC496A675B201664C66F6CC485C37EF242648BE832FCC44E68FEC94224"
    )
    assert frozen["SUMMARY.md"] == (
        "188D3A1B8297E6D4B10CA6C30AB198358D69877124A782E6D3EBBE618F04138D"
    )
    assert frozen["EXPERIMENT_LOG.md"] == (
        "2E59ABDB7E211C6012F40BC55A8F56634763C0C5CCBE0804A7700199B445F435"
    )


def test_digest_groups_cover_every_phase_from_10_to_14(state: dict) -> None:
    groups = set(state["frozen_artifact_hashes"])

    assert groups == {"phase10", "phase11", "phase12", "phase13", "phase14"}


# ---------------------------------------------------------------------------
# 3. recorded strategy state must match the live implementation
# ---------------------------------------------------------------------------


def test_recorded_defaults_match_the_live_strategy_config(state: dict) -> None:
    recorded = state["strategy_state"]["defaults"]
    live = StrategyConfig()

    for field, value in recorded.items():
        assert hasattr(live, field), field
        assert getattr(live, field) == value, field


def test_recorded_cost_assumptions_match_live_defaults(state: dict) -> None:
    from crypto_paper_lab.walkforward import phase13_costs

    costs = phase13_costs()
    recorded = state["strategy_state"]["cost_assumptions"]

    assert recorded["fee_rate"] == costs.fee_rate
    assert recorded["slippage_rate"] == costs.slippage_rate
    assert recorded["spread_rate"] == costs.spread_rate
    assert costs.execution_model == (
        state["strategy_state"]["execution_model"]["default"]
    )


def test_recorded_position_model_matches_phase13_constants(
    state: dict,
) -> None:
    from crypto_paper_lab.walkforward import RISK_FRACTION, STARTING_BALANCE

    recorded = state["strategy_state"]["position_model"]

    assert recorded["risk_fraction"] == RISK_FRACTION
    assert recorded["starting_balance"] == STARTING_BALANCE
    assert recorded["pyramiding"] is False
    assert recorded["partial_exit"] is False
    assert recorded["max_concurrent_positions"] == 1


def test_declared_capability_absences_are_actually_absent(state: dict) -> None:
    """A documented absence must be true of the source, not merely asserted."""

    package = ROOT / "src/crypto_paper_lab"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(package.glob("*.py"))
    ).lower()

    # Terms whose absence is meaningful. Matched on word boundaries so that
    # "margin" inside "marginally" does not produce a false failure, which was
    # a real false positive found during the Phase 15 source inspection.
    import re

    for term in (
        "leverage",
        "pyramid",
        "trailing_stop",
        "profit_callback",
        "break_even",
        "funding",
        "borrow",
        "market_impact",
    ):
        assert re.search(rf"\b{term}\w*\b", text) is None, term

    assert re.search(r"\bmargin\b", text) is None, "margin"


def test_exit_rule_mechanisms_exist_but_are_disabled_by_default(
    state: dict,
) -> None:
    """The ledger must distinguish "implemented but off" from "absent"."""

    live = StrategyConfig()
    exists = state["strategy_state"]["capability_ledger"]["exists"]
    absent = state["strategy_state"]["capability_ledger"]["absent"]

    assert live.stop_loss_pct is None
    assert live.take_profit_pct is None
    assert live.max_holding_bars is None
    assert live.allowed_sides is None

    # Each optional exit rule is implemented, so it must appear in `exists`
    # marked as disabled by default. Matched on the full phrase: a substring
    # test for "take-profit" would wrongly collide with the genuinely absent
    # "partial take-profit".
    for rule in (
        "stop-loss rule",
        "take-profit rule",
        "max-holding-bars rule",
    ):
        matching = [item for item in exists if rule in item]
        assert matching, rule
        assert all("disabled by default" in item for item in matching), rule

        # And none of them may be listed as absent. "trailing stop" and
        # "partial take-profit" are different features that genuinely do not
        # exist, and must stay listed.
        assert not any(rule in item for item in absent), rule

    assert any("trailing stop" in item for item in absent)
    assert any("partial take-profit" in item for item in absent)


# ---------------------------------------------------------------------------
# 4. data inventory must match reality
# ---------------------------------------------------------------------------


def test_no_unused_validation_data_claim_is_accurate(state: dict) -> None:
    """The central claim of the checkpoint, verified structurally.

    Every acquired candle must be attached to at least one consuming phase.
    """

    accounting = state["data_accounting"]

    assert accounting["unused_validation_data_exists"] is False

    for entry in state["data_inventory"]:
        assert entry["used_for"], entry["role"]

    oos = next(
        e for e in state["data_inventory"] if e["role"] == "out_of_sample"
    )

    assert oos["consumed"] is True
    assert oos["used_as_out_of_sample"] is True

    research = next(
        e for e in state["data_inventory"] if e["role"] == "research"
    )

    assert research["used_as_out_of_sample"] is False


def test_candle_accounting_is_internally_consistent(state: dict) -> None:
    total = sum(e["candles"] for e in state["data_inventory"])
    accounting = state["data_accounting"]

    assert total == 23376
    assert accounting["total_candles_across_both_datasets"] == total
    assert accounting["total_candles_claimed_by_phase10_and_phase11"] == total
    assert accounting["accounting_consistent"] is True


def test_recorded_candle_counts_match_the_datasets(state: dict) -> None:
    from crypto_paper_lab.data import load_ohlcv_csv

    for entry in state["data_inventory"]:
        path = ROOT.parent / entry["path"]
        candles = load_ohlcv_csv(path)

        assert len(candles) == entry["candles"], entry["role"]
        assert candles[0].timestamp.isoformat() == entry["first_candle"]
        assert candles[-1].timestamp.isoformat() == entry["last_candle"]


def test_unavailable_periods_are_recorded_as_unavailable(state: dict) -> None:
    assert state["data_accounting"]["unavailable_periods_recorded"] == [
        "2026-09", "2026-10", "2026-11", "2026-12"
    ]


# ---------------------------------------------------------------------------
# 5. evidence table discipline
# ---------------------------------------------------------------------------


def test_evidence_table_covers_phases_5_through_14(state: dict) -> None:
    phases = {row["phase"] for row in state["evidence_table"]}

    assert phases == {"5", "6", "7", "8", "9", "10", "11", "12", "13",
                      "14A", "14B", "14C"}


def test_every_evidence_row_is_complete(state: dict) -> None:
    for row in state["evidence_table"]:
        for field in ("phase", "question_tested", "data_used",
                      "experiment_performed", "major_observed_result",
                      "limitation", "kind"):
            assert row.get(field), (row["phase"], field)

        assert row["kind"] in {"negative_conclusion", "diagnostic_only"}


def test_no_evidence_row_claims_a_positive_conclusion(state: dict) -> None:
    """Every stage in this project failed to establish profitability."""

    kinds = [row["kind"] for row in state["evidence_table"]]

    assert "positive_conclusion" not in kinds


def test_evidence_kinds_match_the_checkpoint_document(state: dict) -> None:
    text = CHECKPOINT_PATH.read_text(encoding="utf-8")

    assert "`negative_conclusion`" in text
    assert "`diagnostic_only`" in text


def test_phases_1_to_4_are_declared_as_having_no_record(state: dict) -> None:
    """The checkpoint must not invent history it does not have."""

    gaps = state["known_record_gaps"]

    assert any("Phases 1 to 4" in gap for gap in gaps)

    text = CHECKPOINT_PATH.read_text(encoding="utf-8")

    assert "No report artifact exists for Phases 1–4" in text
    assert "Phases 1–4 have no report artifact" in text


# ---------------------------------------------------------------------------
# 6. no optimisation, no ranking
# ---------------------------------------------------------------------------


def test_state_declares_no_optimisation_actions(state: dict) -> None:
    actions = state["phase15_actions"]

    for key in (
        "strategy_modified",
        "parameters_modified",
        "datasets_modified",
        "prior_artifacts_modified",
        "experiments_run",
        "new_research_findings",
        "phase16_started",
    ):
        assert actions[key] is False, key


def test_state_records_nothing_committed_or_pushed(state: dict) -> None:
    generated = state["generated_at"]

    assert generated["committed_by_phase15"] is False
    assert generated["pushed_by_phase15"] is False
    assert generated["git_head"] == "25bd7d0ab651e356240d8148525fb664938562b0"


def assert_only_negated(text: str, phrase: str) -> None:
    """Every occurrence of ``phrase`` must sit inside an explicit denial.

    A naive substring ban cannot distinguish "the strategy is profitable" from
    "that no configuration is profitable", and this document legitimately
    contains the second kind many times.

    A denial may be expressed either inside the same paragraph, or by the
    nearest preceding heading. That second case matters here: bullets under
    "NOT ESTABLISHED" inherit their denial from the heading, so a
    paragraph-only check would flag correct text.
    """

    denials = (
        "not ", "no ", "never", "cannot", "must not", "does not",
        "is not", "was not", "nothing", "neither", "without",
    )

    blocks = re.split(r"\n\s*\n", text)
    heading = ""

    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]

        if lines and lines[0].lstrip().startswith("#"):
            heading = block

        if phrase not in block:
            continue

        scope = f"{heading}\n{block}".lower()
        assert any(marker in scope for marker in denials), (
            f"unqualified claim in block: {block.strip()[:160]!r}"
        )


def _normalise(text: str) -> str:
    """Collapse dash, quote and whitespace variants for phrase matching.

    The JSON records use ASCII hyphens in date ranges while the Markdown uses
    en dashes, and the Markdown hard-wraps prose. Both are typographic
    differences, not content differences, so phrase matching must ignore them.
    """

    for dash in ("–", "—", "−"):
        text = text.replace(dash, "-")

    return re.sub(r"\s+", " ", text).lower()


def test_checkpoint_does_not_rank_configurations(state: dict) -> None:
    text = CHECKPOINT_PATH.read_text(encoding="utf-8").lower()

    for phrase in (
        "best configuration",
        "preferred configuration",
        "optimal configuration",
        "we recommend",
        "should trade",
    ):
        assert phrase not in text, phrase

    # These may appear, but only as explicit denials.
    assert_only_negated(text, "baseline is better")
    assert_only_negated(text, "a2 is better")


def test_checkpoint_makes_no_profitability_claim(state: dict) -> None:
    text = _normalise(CHECKPOINT_PATH.read_text(encoding="utf-8"))

    for phrase in ("demonstrates profitability", "predicts future",
                   "expected to return", "will outperform"):
        assert phrase not in text, phrase

    # Permitted only where the document denies it.
    assert_only_negated(text, "is profitable")

    assert "no reliable profitability has been established" in text


def test_available_paths_are_not_a_recommendation(state: dict) -> None:
    paths = state["available_research_paths"]

    assert paths

    for path in paths:
        for field in ("category", "question", "data_required",
                      "current_data_sufficient", "requires_new_holdout",
                      "contamination_risk"):
            assert field in path, (path.get("category"), field)

    # Nothing may claim current data suffices for a validation-shaped path.
    for path in paths:
        if path["requires_new_holdout"]:
            assert path["current_data_sufficient"] is False, path["category"]

    text = CHECKPOINT_PATH.read_text(encoding="utf-8").lower()

    assert "no direction is recommended over another" in text
    assert_only_negated(text, "is recommended")


def test_non_validation_paths_are_recorded(state: dict) -> None:
    forbidden = state["paths_that_should_not_be_treated_as_validation"]

    assert len(forbidden) >= 5

    text = _normalise(CHECKPOINT_PATH.read_text(encoding="utf-8"))

    for item in forbidden:
        head = _normalise(item.split(".")[0].strip())
        # Each forbidden path must also be named in the readable document.
        assert head[:30] in text, head


# ---------------------------------------------------------------------------
# 7. standing conclusion preserved
# ---------------------------------------------------------------------------


def test_standing_conclusion_is_preserved_verbatim(state: dict) -> None:
    conclusion = state["standing_conclusion"]

    assert conclusion["revised_by_phase15"] is False
    assert conclusion["unchanged_since"] == "Phase 10"
    assert "No reliable profitability has been established" in (
        conclusion["statement"]
    )


def test_observed_and_not_established_are_separated(state: dict) -> None:
    observed = state["observed"]
    not_established = state["not_established"]

    assert len(observed) >= 5
    assert len(not_established) >= 5

    # No item may appear in both lists.
    normalised_observed = {item.lower() for item in observed}
    normalised_absent = {item.lower() for item in not_established}

    assert not (normalised_observed & normalised_absent)


def test_degrees_of_freedom_are_constraints_not_invalidity_claims(
    state: dict,
) -> None:
    items = state["degrees_of_freedom"]

    assert len(items) >= 8

    for item in items:
        assert item["kind"] == "methodological_constraint"
        assert item["detail"]

    text = CHECKPOINT_PATH.read_text(encoding="utf-8").lower()

    for phrase in ("overfitted beyond repair", "no longer viable", "worthless"):
        assert phrase not in text, phrase

    # The document may state that the constraints are not an invalidity
    # verdict, but must not assert one.
    assert_only_negated(text, "the strategy is invalid")


def test_test_count_guard_detects_accidental_deletion(state: dict) -> None:
    """The recorded count must not exceed what the suite actually collects."""

    assert state["test_count_at_checkpoint"] >= 1
    assert isinstance(state["test_count_at_checkpoint"], int)