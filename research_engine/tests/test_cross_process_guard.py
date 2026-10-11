"""Cross-process verification of the registry lock and single-use semantics.

Phase 56 verified exclusion with threads inside one interpreter. That is not
sufficient evidence: threads share a process, and ``O_CREAT | O_EXCL`` exclusion
is claimed at the *operating system* level. These tests spawn genuinely
independent OS processes and race them against each other.

Everything runs against a temporary registry holding synthetic reservations. The
real ``data/research_registry.json`` and the reserved ETH dataset are never
written or evaluated; one test asserts that explicitly.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

import pytest

from crypto_paper_lab.researchguard import (
    _REGISTRY_LOCK_SUFFIX,
    ResearchGuardError,
    _registry_lock,
    consume_reservation,
)


ROOT = Path(__file__).resolve().parents[1]
REAL_REGISTRY = ROOT / "data" / "research_registry.json"
REAL_ETH_CSV = ROOT / "data" / "phase33" / "binance_spot_ETHUSDT_1h_202401-202610.csv"

# Spawned children re-import this module, so ``src`` must be importable for them.
sys.path.insert(0, str(ROOT / "src"))


def _registry(tmp_path: Path, *ids: str) -> Path:
    """Schema-valid registry holding synthetic, unspent reservations."""

    reg = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    template = next(
        e for e in reg["reservations"] if e["reservation_id"] == "ETH-2026-RESERVATION"
    )
    for rid in ids:
        probe = dict(template)
        probe["reservation_id"] = rid
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


def _entry(path: Path, rid: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return next(e for e in data["reservations"] if e["reservation_id"] == rid)


def _lock_path(path: Path) -> Path:
    return path.with_name(path.name + _REGISTRY_LOCK_SUFFIX)


# --------------------------------------------------------------------------
# worker executed in a genuinely separate OS process
# --------------------------------------------------------------------------


def _consume_worker(
    registry: str,
    reservation_id: str,
    preregistration_id: str,
    gate_path: str,
    result_path: str,
) -> None:
    """Child process: wait on a gate file, then race to consume."""

    # Busy-wait on the gate so every child starts at as near the same instant as
    # the scheduler allows.
    deadline = time.time() + 30
    while not os.path.exists(gate_path):
        if time.time() > deadline:
            return
        time.sleep(0.001)

    outcome = "consumed"
    try:
        consume_reservation(
            reservation_id,
            registry_file=registry,
            preregistration_id=preregistration_id,
        )
    except ResearchGuardError as exc:
        outcome = f"refused:{type(exc).__name__}"
    except Exception as exc:  # pragma: no cover - surfaced as a test failure
        outcome = f"error:{type(exc).__name__}:{exc}"

    Path(result_path).write_text(
        f"{os.getpid()}|{preregistration_id}|{outcome}", encoding="utf-8"
    )


def _lock_hold_worker(registry: str, hold_path: str, release_path: str,
                      ready_path: str) -> None:
    """Child process: hold the lock until told to release, then exit.

    The deadline is deliberately short. The lock itself is never released here
    -- that is what ``test_interrupted_holder...`` relies on -- so a killed or
    timed-out holder leaves an orphaned lock file behind, which is the state
    under test.
    """

    target = Path(registry)
    with _registry_lock(target):
        Path(hold_path).write_text(str(os.getpid()), encoding="utf-8")
        Path(ready_path).write_text("1", encoding="utf-8")
        deadline = time.time() + 8
        while not os.path.exists(release_path):
            if time.time() > deadline:
                break
            time.sleep(0.005)
    if os.path.exists(release_path):
        Path(hold_path).write_text("released", encoding="utf-8")


# --------------------------------------------------------------------------
# cross-process contention
# --------------------------------------------------------------------------


def _run_race(
    tmp_path: Path, reservation_id: str, contenders: int
) -> list[str]:
    """Race ``contenders`` independent processes on one synthetic reservation."""

    path = _registry(tmp_path, reservation_id)
    gate = tmp_path / "gate"
    results = tmp_path / "results"
    results.mkdir(exist_ok=True)

    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(
            target=_consume_worker,
            args=(str(path), reservation_id, f"pre-{n}", str(gate),
                  str(results / f"r{n}")),
        )
        for n in range(contenders)
    ]
    for proc in procs:
        proc.start()
    # Let every child import the module and reach the gate before releasing it,
    # so the contention window is as tight as the scheduler allows.
    time.sleep(0.6 + 0.15 * contenders)
    gate.write_text("go", encoding="utf-8")
    for proc in procs:
        proc.join(timeout=60)

    written = sorted(results.iterdir())
    assert len(written) == contenders, "every child must report an outcome"
    return [p.read_text(encoding="utf-8") for p in written]


def _outcome(report: str) -> str:
    return report.split("|")[2]


def _pre(report: str) -> str:
    return report.split("|")[1]


def _pid(report: str) -> str:
    return report.split("|")[0]


def test_two_processes_racing_one_reservation_exactly_one_wins(tmp_path: Path) -> None:
    """Independent OS processes: exactly one consumes, one is refused."""

    reports = _run_race(tmp_path, "XPROC", 2)
    outcomes = sorted(_outcome(r) for r in reports)

    assert len(outcomes) == 2, outcomes
    assert outcomes.count("consumed") == 1, f"exactly one must win, got {outcomes}"
    assert outcomes.count("refused:ResearchGuardError") == 1, (
        f"the loser must be refused by the guard, got {outcomes}"
    )

    assert len({_pid(r) for r in reports}) == 2, (
        "results must come from two distinct processes"
    )


def test_winning_preregistration_is_recorded_and_not_overwritten(tmp_path: Path) -> None:
    """The surviving audit record belongs to the single winner, not a blend."""

    reports = _run_race(tmp_path, "XPROC", 2)
    winner = next(r for r in reports if _outcome(r) == "consumed")

    spent = _entry(tmp_path / "registry.json", "XPROC")
    assert spent["used"] is True
    assert spent["status"] == "USED"
    assert spent["used_preregistration_id"] == _pre(winner), (
        "the recorded preregistration must be the winner's, not the loser's"
    )
    assert spent["used_on"], "the winner's timestamp must be recorded"


def test_four_processes_still_produce_exactly_one_winner(tmp_path: Path) -> None:
    """Contention widens; the invariant must hold."""

    reports = _run_race(tmp_path, "XPROC", 4)
    outcomes = [_outcome(r) for r in reports]
    assert outcomes.count("consumed") == 1, outcomes
    assert outcomes.count("refused:ResearchGuardError") == 3, outcomes


def test_distinct_processes_never_corrupt_the_registry(tmp_path: Path) -> None:
    """Two processes consuming *different* reservations must stay consistent.

    The lock is fail-closed with **no wait**: a process arriving while the lock
    is held is refused rather than queued. That is a deliberate safety choice,
    and its cost is that concurrent distinct work can refuse spuriously. This
    test therefore asserts the safety property, not that both succeed:

    * the registry is always parseable and internally consistent;
    * a reservation is either fully spent or fully unspent -- never half-written;
    * at least one attempt gets through.
    """

    path = _registry(tmp_path, "X-A", "X-B")
    gate = tmp_path / "gate"
    results = tmp_path / "results"
    results.mkdir(exist_ok=True)
    gate.write_text("go", encoding="utf-8")

    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(
            target=_consume_worker,
            args=(str(path), rid, f"pre-{rid}", str(gate),
                  str(results / f"done-{rid}")),
        )
        for rid in ("X-A", "X-B")
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=60)

    outcomes = [p.read_text(encoding="utf-8").split("|")[2]
                for p in results.iterdir()]
    assert outcomes.count("consumed") >= 1, outcomes
    assert all(o in {"consumed"} or o.startswith("refused:") for o in outcomes), outcomes

    data = json.loads(path.read_text(encoding="utf-8"))  # always valid JSON
    for rid in ("X-A", "X-B"):
        entry = next(e for e in data["reservations"] if e["reservation_id"] == rid)
        # The invariant that must hold no matter who won: the flag and the
        # status agree, and there is never a partially-applied spend.
        assert entry["used"] is (entry["status"] == "USED")
        if entry["used"]:
            assert entry["used_preregistration_id"] == f"pre-{rid}"
            assert entry["used_on"]
        else:
            assert entry.get("used_preregistration_id") is None
            assert "used_on" not in entry

    spent = [r for r in data["reservations"] if r["reservation_id"] in {"X-A", "X-B"}
             and r["used"]]
    assert len(spent) == outcomes.count("consumed"), (
        "each success must correspond to exactly one spent reservation"
    )
    # The sidecar persists by design (deleting it would race an opener). What
    # must not persist is a *held* lock, so re-acquire to prove it is free.
    with _registry_lock(path):
        pass  # re-acquiring proves the lock was released


def _write_lock(path: Path, pid: str, age_seconds: float) -> Path:
    """Plant a lock file attributed to ``pid`` and backdate it by ``age_seconds``."""

    lock = _lock_path(path)
    lock.write_text(f"pid={pid} at={time.strftime('%Y-%m-%dT%H:%M:%S')}\n",
                    encoding="utf-8")
    when = time.time() - age_seconds
    os.utime(lock, (when, when))
    return lock







def test_read_failure_fails_closed_without_writing(tmp_path: Path) -> None:
    """An unreadable registry must raise and leave nothing behind."""

    path = _registry(tmp_path, "X-LOCK")
    path.unlink()
    with pytest.raises(Exception):
        consume_reservation("X-LOCK", registry_file=path, preregistration_id="pre")
    assert not _lock_path(path).exists(), "no lock may leak on failure"
    assert not path.exists(), "a missing registry must not be recreated"


def test_lock_directory_unwritable_fails_closed(tmp_path: Path) -> None:
    """If the lock cannot be created, consumption must refuse, not proceed."""

    path = _registry(tmp_path, "X-LOCK")
    holder = _lock_path(path)
    holder.mkdir()  # a directory cannot be opened with O_EXCL -> raises

    try:
        with pytest.raises(ResearchGuardError):
            with _registry_lock(path):
                pass  # pragma: no cover
    finally:
        holder.rmdir()
    assert _entry(path, "X-LOCK")["used"] is False


def test_real_eth_reservation_untouched_by_all_cross_process_work(
    tmp_path: Path,
) -> None:
    before = REAL_REGISTRY.read_text(encoding="utf-8")

    path = _registry(tmp_path, "XPROC")
    gate = tmp_path / "gate"
    results = tmp_path / "results"
    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(
            target=_consume_worker,
            args=(str(path), "XPROC", f"pre-{n}", str(gate), str(results / f"r{n}")),
        )
        for n in range(2)
    ]
    for proc in procs:
        proc.start()
    time.sleep(0.6)
    gate.write_text("go", encoding="utf-8")
    for proc in procs:
        proc.join(timeout=60)

    assert REAL_REGISTRY.read_text(encoding="utf-8") == before
    real = next(
        e
        for e in json.loads(before)["reservations"]
        if e["reservation_id"] == "ETH-2026-RESERVATION"
    )
    assert real["status"] == "RESERVED"
    assert real["used"] is False
    assert real["preregistration_id"] is None
    assert "used_on" not in real
    assert "used_preregistration_id" not in real
    assert REAL_ETH_CSV.exists()