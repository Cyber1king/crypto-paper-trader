"""Single-use reservation semantics.

A reservation is spent exactly once. Re-spending it must be refused rather than
silently accepted, because re-spending overwrites ``used_on`` and
``used_preregistration_id`` -- the only durable record of *when* the window was
evaluated and *under which preregistration*.

Every test here uses a temporary registry containing a synthetic reservation.
The real ``data/research_registry.json`` and the reserved ETH dataset are never
opened, written or evaluated.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_paper_lab.researchguard import (
    ResearchGuardError,
    consume_reservation,
)


ROOT = Path(__file__).resolve().parents[1]
REAL_REGISTRY = ROOT / "data" / "research_registry.json"
REAL_ETH_CSV = ROOT / "data" / "phase33" / "binance_spot_ETHUSDT_1h_202401-202610.csv"


def _probe_registry(tmp_path: Path) -> Path:
    """A schema-valid registry copy holding one *synthetic* unspent reservation.

    The real registry is read (never written) purely to inherit a valid
    instrument block; ``load_registry`` refuses an empty registry, which is the
    fail-closed behaviour the schema intends.
    """

    reg = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    template = next(
        e for e in reg["reservations"] if e["reservation_id"] == "ETH-2026-RESERVATION"
    )

    probe = dict(template)
    probe["reservation_id"] = "PROBE-SYNTHETIC"
    probe["instrument_id"] = "BTC/USDT"
    probe["used"] = False
    probe["status"] = "RESERVED"
    probe["preregistration_id"] = None
    probe.pop("used_on", None)
    probe.pop("used_preregistration_id", None)
    reg["reservations"].append(probe)

    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg, indent=2), encoding="utf-8")
    return path


def _entry(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return next(
        e for e in data["reservations"] if e["reservation_id"] == "PROBE-SYNTHETIC"
    )


def test_first_consumption_spends_the_reservation(tmp_path: Path) -> None:
    path = _probe_registry(tmp_path)

    consume_reservation("PROBE-SYNTHETIC", registry_file=path, preregistration_id="pre-A")

    spent = _entry(path)
    assert spent["used"] is True
    assert spent["status"] == "USED"
    assert spent["used_preregistration_id"] == "pre-A"
    assert spent["used_on"]


def test_second_consumption_is_rejected(tmp_path: Path) -> None:
    path = _probe_registry(tmp_path)
    consume_reservation("PROBE-SYNTHETIC", registry_file=path, preregistration_id="pre-A")

    with pytest.raises(ResearchGuardError, match="already spent"):
        consume_reservation("PROBE-SYNTHETIC", registry_file=path, preregistration_id="pre-B")


def test_rejected_second_consumption_preserves_the_audit_trail(tmp_path: Path) -> None:
    """The original spend record must survive a rejected re-spend byte for byte."""

    path = _probe_registry(tmp_path)
    consume_reservation("PROBE-SYNTHETIC", registry_file=path, preregistration_id="pre-A")

    before = path.read_text(encoding="utf-8")
    spent_before = _entry(path)

    with pytest.raises(ResearchGuardError):
        consume_reservation("PROBE-SYNTHETIC", registry_file=path, preregistration_id="pre-B")

    assert path.read_text(encoding="utf-8") == before
    assert _entry(path)["used_preregistration_id"] == "pre-A"
    assert _entry(path)["used_on"] == spent_before["used_on"]


def test_rejection_happens_before_any_mutation_of_a_multi_reservation_call(
    tmp_path: Path,
) -> None:
    """If any requested reservation is already spent, none of them are touched."""

    path = _probe_registry(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    spare = dict(data["reservations"][0])
    spare["reservation_id"] = "PROBE-UNSPENT"
    spare["used"] = False
    spare["status"] = "RESERVED"
    spare["preregistration_id"] = None
    spare.pop("used_on", None)
    spare.pop("used_preregistration_id", None)
    data["reservations"].append(spare)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    consume_reservation("PROBE-SYNTHETIC", registry_file=path, preregistration_id="pre-A")

    before = path.read_text(encoding="utf-8")
    with pytest.raises(ResearchGuardError, match="already spent"):
        consume_reservation(
            "PROBE-SYNTHETIC",
            registry_file=path,
            preregistration_id="pre-B",
        )
    assert path.read_text(encoding="utf-8") == before


def test_consumption_without_a_registry_file_fails_closed() -> None:
    """Omitting ``registry_file`` must refuse, and must not write the real registry.

    ``consume_reservation`` resolves the reservation before it checks for a
    writable target, so the real ETH reservation id is used here precisely
    because it *does* resolve -- that is the path which reaches the
    ``no registry_file`` refusal. The refusal happens before any mutation, so the
    reserved window is not spent.
    """

    before = REAL_REGISTRY.read_text(encoding="utf-8")

    with pytest.raises(ResearchGuardError, match="no registry_file"):
        consume_reservation("ETH-2026-RESERVATION")

    assert REAL_REGISTRY.read_text(encoding="utf-8") == before


def test_unknown_reservation_is_still_rejected(tmp_path: Path) -> None:
    path = _probe_registry(tmp_path)
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ResearchGuardError, match="not in the registry"):
        consume_reservation("NO-SUCH-RESERVATION", registry_file=path)

    assert path.read_text(encoding="utf-8") == before


def test_real_eth_reservation_is_never_touched_by_this_module(tmp_path: Path) -> None:
    """Guard: the reserved ETH window must still be unspent after this module."""

    before = REAL_REGISTRY.read_text(encoding="utf-8")
    path = _probe_registry(tmp_path)

    consume_reservation("PROBE-SYNTHETIC", registry_file=path, preregistration_id="pre-A")
    with pytest.raises(ResearchGuardError):
        consume_reservation("PROBE-SYNTHETIC", registry_file=path, preregistration_id="pre-B")

    assert REAL_REGISTRY.read_text(encoding="utf-8") == before
    real = next(
        e
        for e in json.loads(before)["reservations"]
        if e["reservation_id"] == "ETH-2026-RESERVATION"
    )
    assert real["status"] == "RESERVED"
    assert real["used"] is False
    assert real["preregistration_id"] is None
    assert REAL_ETH_CSV.exists()