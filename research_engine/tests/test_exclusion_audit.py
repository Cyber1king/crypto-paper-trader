"""Phase 105: validate the exclusion audit without running any excluded test.

Two real defects were found by validating the artifact and are pinned here:

1. The reserved-ETH flag was computed inside the per-file loop but read after
   it, so every one of the 1,087 records inherited the *last* file's value and
   reported zero reserved-ETH exposure. That is a safety-relevant finding
   silently cleared by a variable that was simply read in the wrong place.

2. Records carried no ``test`` name, so an audit row could not name the test it
   excluded without re-parsing ``node_id``.

These tests parse the artifact and re-derive its claims from the repository. No
excluded test is executed, and no reserved-period value is read.
"""
from __future__ import annotations

import ast
import collections
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments" / "phase101" / "excluded_test_audit.json"
GENERATOR = ROOT / "experiments" / "phase101" / "generate_audit.py"

REQUIRED_RECORD_FIELDS = {
    "node_id",
    "file",
    "test",
    "entry_points",
    "touches_reserved_eth",
    "data_source",
    "calls_prohibited_operation",
    "disposition",
    "reason",
}


_SOURCE_CACHE: dict[str, str] = {}


def _source(name: str) -> str:
    """Read a test file once.

    The audit has one record per test but only a handful of files, so reading
    per record re-read the same 83 KB file hundreds of times.
    """

    if name not in _SOURCE_CACHE:
        _SOURCE_CACHE[name] = (ROOT / "tests" / f"{name}.py").read_text(encoding="utf-8")
    return _SOURCE_CACHE[name]


@pytest.fixture(scope="module")
def audit() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def records(audit: dict) -> list[dict]:
    return audit["tests"]


# 1. schema
def test_the_artifact_exists_and_parses(audit: dict) -> None:
    assert ARTIFACT.exists()
    assert audit["counts"] and audit["tests"]


def test_top_level_schema_is_complete(audit: dict) -> None:
    assert {
        "generated_for",
        "method",
        "forbidden_entry_points",
        "counts",
        "by_file",
        "tests",
    } <= set(audit)


def test_every_record_carries_every_required_field(records: list[dict]) -> None:
    """Defect 2: records previously had no ``test`` name."""

    incomplete = [
        r["node_id"] for r in records if not REQUIRED_RECORD_FIELDS <= set(r)
    ]
    assert incomplete == [], f"records missing fields: {incomplete[:5]}"


def test_every_record_names_its_test(records: list[dict]) -> None:
    for record in records:
        assert record["test"].startswith("test_")
        assert record["file"].startswith("test_")


# 2. totals reconcile
def test_record_count_matches_the_declared_total(audit: dict, records) -> None:
    assert audit["counts"]["evaluation_touching_node_ids"] == len(records)


def test_unique_count_matches_a_recomputation(audit: dict, records) -> None:
    ids = [r["node_id"] for r in records]
    assert audit["counts"]["unique_node_ids"] == len(set(ids))


def test_duplicates_are_declared_accurately(audit: dict, records) -> None:
    ids = [r["node_id"] for r in records]
    actual = [i for i, c in collections.Counter(ids).items() if c > 1]
    assert audit["counts"]["duplicate_node_ids"] == actual


def test_by_file_matches_a_recomputation(audit: dict, records) -> None:
    recomputed = dict(sorted(collections.Counter(r["file"] for r in records).items()))
    assert audit["by_file"] == recomputed


def test_by_file_keys_are_exactly_the_recorded_files(audit: dict, records) -> None:
    assert set(audit["by_file"]) == {r["file"] for r in records}


def test_node_id_format_is_consistent(records: list[dict]) -> None:
    for record in records:
        parts = record["node_id"].split("::")
        assert len(parts) in (2, 3), record["node_id"]
        assert parts[0] == record["file"]


def test_the_node_id_embeds_the_test_name(records: list[dict]) -> None:
    for record in records:
        assert record["test"] in record["node_id"]


# 3. reserved-ETH flag, independently re-derived
def test_reserved_flag_is_recomputable_from_the_source_file(records) -> None:
    """Defect 1: the flag was read after the loop and inherited the wrong file.

    Re-derived here straight from each test file, independently of how the
    artifact was produced.
    """

    misflagged = []
    for record in records:
        assert (ROOT / "tests" / f"{record['file']}.py").exists(), (
            f"{record['node_id']}: source file missing"
        )
        text = _source(record["file"])
        expected = ("phase33" in text) or ("ETHUSDT" in text)
        if expected != record["touches_reserved_eth"]:
            misflagged.append((record["node_id"], expected))
    assert misflagged == [], f"reserved-ETH flag wrong for {misflagged[:5]}"


def test_exactly_five_records_touch_the_reserved_dataset(audit, records) -> None:
    flagged = [r for r in records if r["touches_reserved_eth"]]
    assert len(flagged) == 5
    assert audit["counts"]["touches_reserved_eth"] == 5
    assert {r["file"] for r in flagged} == {"test_research_gaps"}


def test_the_five_reserved_records_are_the_expected_guards(records) -> None:
    flagged = sorted(r["node_id"] for r in records if r["touches_reserved_eth"])
    assert flagged == sorted(
        [
            "test_research_gaps::test_run_backtest_refuses_reserved_series_without_context",
            "test_research_gaps::test_replay_refuses_reserved_series_without_context",
            "test_research_gaps::test_run_experiment_refuses_reserved_series_without_context",
            "test_research_gaps::test_run_yearly_refuses_reserved_series_without_context",
            "test_research_gaps::test_reserved_dates_alone_do_not_refuse_synthetic",
        ]
    )


def test_a_reserved_record_says_so_in_its_reason(records) -> None:
    for record in records:
        if record["touches_reserved_eth"]:
            assert "reserved ETH" in record["reason"]
            assert record["data_source"] == "reserved_eth"


def test_no_record_exposes_protected_period_values(records) -> None:
    """The audit is an index, not a cache of anything protected."""

    # A test NAME may legitimately contain "entry_price" or "realized_pnl",
    # so matching raw text would flag its own vocabulary. What must not appear
    # is a protected-period *value*, so this checks the structure: no field of
    # any record may carry market data.
    forbidden_fields = {
        "close", "high", "low", "open", "volume",
        "close_price", "entry_price", "exit_price",
        "realized_pnl", "profit_factor", "balance", "trades",
    }
    leaked = sorted(
        {k for record in records for k in record if k in forbidden_fields}
    )
    assert leaked == [], f"audit carries market data fields: {leaked}"

    # And no record may hold a long numeric payload that could be a price.
    for record in records:
        for key, value in record.items():
            if isinstance(value, list) and key != "entry_points":
                assert not any(isinstance(v, (int, float)) for v in value), (
                    f"{record['node_id']}.{key} looks like market data"
                )


# 4. the generator itself
def test_the_generator_writes_the_same_fields_the_artifact_has() -> None:
    """Static equivalence, by design rather than execution.

    The generator is *not* imported and run here: doing so regenerates the
    artifact as a side effect of a test, which makes the audit a function of
    test order. Its output contract is checked against the artifact instead.
    """

    source = GENERATOR.read_text(encoding="utf-8")
    for field in REQUIRED_RECORD_FIELDS:
        assert f'"{field}"' in source, f"{field} not emitted by the generator"
    assert '"tests": entries' in source


def test_the_generator_derives_its_counts_rather_than_hardcoding_them() -> None:
    source = GENERATOR.read_text(encoding="utf-8")
    # Counts that were typed in by hand are how the original artifact came to
    # disagree with itself; these must be computed from the entries.
    assert "len(entries)" in source
    assert "len(set(ids))" in source
    assert "collections.Counter(ids)" in source


def test_the_generator_runs_no_tests() -> None:
    """Static analysis only: importing it must not execute a test module."""

    source = GENERATOR.read_text(encoding="utf-8")
    for forbidden in ("pytest.main", "subprocess", "os.system", "run_backtest("):
        assert forbidden not in source


def test_the_generator_reads_the_reserved_flag_inside_the_file_loop() -> None:
    """Guard against defect 1 returning.

    The flag must be computed per file and stored on each record, not read
    from a loop variable after the loop has moved on.
    """

    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    analyses = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "analyse"
    ]
    assert analyses, "analyse() not found"
    body = ast.unparse(analyses[0])
    assert "reserved = " in body
    # It must be threaded into the record builder rather than re-derived later,
    # which is how the original artifact inherited the wrong file's value.
    assert '"touches_reserved_eth": reserved' in GENERATOR.read_text(encoding="utf-8")


# 5. reconciliation note
def test_the_artifact_records_the_count_reconciliation(audit: dict) -> None:
    assert "152" in audit["counts"]["reconciliation"]
    assert "579" in audit["counts"]["reconciliation"]


def test_every_excluded_record_is_marked_excluded(records) -> None:
    assert all(r["disposition"] == "EXCLUDED" for r in records)
    assert all(r["calls_prohibited_operation"] is True for r in records)


def test_entry_points_are_all_forbidden_operations(audit: dict, records) -> None:
    allowed = set(audit["forbidden_entry_points"])
    for record in records:
        assert record["entry_points"], record["node_id"]
        assert set(record["entry_points"]) <= allowed