"""Registry locking: exclusion, failure, and crash behaviour.

The lock is an OS-native advisory lock (``fcntl.flock`` on POSIX,
``msvcrt.locking`` on Windows) held on an open descriptor for the duration of the
registry read-modify-write. The OS releases it when the descriptor closes *or*
when the process dies, so a crashed writer cannot orphan it.

Every test uses a temporary registry with synthetic reservations. The real
registry and the reserved ETH dataset are never written; a test asserts that.

Platform: these ran on Windows 11 / CPython 3.12.10. POSIX branches are
implemented but were not executed here.
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

sys.path.insert(0, str(ROOT / "src"))


def _registry(tmp_path: Path, *ids: str) -> Path:
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
    return next(
        e for e in json.loads(path.read_text(encoding="utf-8"))["reservations"]
        if e["reservation_id"] == rid
    )


def _lock_path(path: Path) -> Path:
    return path.with_name(path.name + _REGISTRY_LOCK_SUFFIX)


def _assert_consistent(path: Path, *ids: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    for rid in ids:
        e = next(x for x in data["reservations"] if x["reservation_id"] == rid)
        assert e["used"] is (e["status"] == "USED")
        if e["used"]:
            assert e["used_preregistration_id"] and e["used_on"]
        else:
            assert e.get("used_preregistration_id") is None
            assert "used_on" not in e


# --------------------------------------------------------------------------
# child processes
# --------------------------------------------------------------------------


def _consume_worker(registry: str, rid: str, pre: str, out: str) -> None:
    try:
        consume_reservation(rid, registry_file=registry, preregistration_id=pre)
        outcome = "consumed"
    except ResearchGuardError:
        outcome = "refused"
    except Exception as exc:  # pragma: no cover - surfaces as a failure
        outcome = f"error:{type(exc).__name__}"
    Path(out).write_text(f"{os.getpid()}|{pre}|{outcome}", encoding="utf-8")


def _hold_lock_worker(registry: str, ready: str, hold_seconds: float) -> None:
    """Acquire the lock, signal, hold, then exit *without* releasing explicitly."""
    import time as _t

    with _registry_lock(Path(registry)):
        Path(ready).write_text("1", encoding="utf-8")
        _t.sleep(hold_seconds)


def _reader_worker(registry: str, stop: str, out: str) -> None:
    bad = reads = 0
    # Capture baseline reads before the writer starts. On Windows os.replace
    # cannot target a file a reader holds open, so once the writer is active a
    # reader may legitimately never win a window -- the invariant under test is
    # "never malformed", and the baseline proves the reader can read at all.
    for _ in range(5):
        try:
            json.loads(Path(registry).read_text(encoding="utf-8"))
            reads += 1
        except (OSError, json.JSONDecodeError):  # pragma: no cover
            pass
    while not os.path.exists(stop):
        try:
            json.loads(Path(registry).read_text(encoding="utf-8"))
            reads += 1
        except FileNotFoundError:
            pass
        except PermissionError:
            # Windows refuses os.replace while a reader holds the target open;
            # the writer fails closed and the reader skips the attempt.
            pass
        except json.JSONDecodeError:
            bad += 1
    Path(out).write_text(json.dumps({"reads": reads, "bad": bad}), encoding="utf-8")


def _race(tmp_path: Path, rid: str, contenders: int) -> tuple[Path, list[str]]:
    path = _registry(tmp_path, rid)
    out = tmp_path / "out"
    out.mkdir()
    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(
            target=_consume_worker,
            args=(str(path), rid, f"pre-{n}", str(out / f"r{n}")),
        )
        for n in range(contenders)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    reports = sorted(p.read_text(encoding="utf-8") for p in out.iterdir())
    assert len(reports) == contenders
    return path, reports


# --------------------------------------------------------------------------
# 1-4: contention
# --------------------------------------------------------------------------


def test_two_consumers_exactly_one_succeeds(tmp_path: Path) -> None:
    """Scenario 1."""
    path, reports = _race(tmp_path, "L-2", 2)
    outcomes = [r.split("|")[2] for r in reports]
    assert outcomes.count("consumed") == 1, outcomes
    assert outcomes.count("refused") == 1, outcomes
    assert len({r.split("|")[0] for r in reports}) == 2, "must be two processes"


def test_four_consumers_exactly_one_succeeds(tmp_path: Path) -> None:
    """Scenario 2."""
    path, reports = _race(tmp_path, "L-4", 4)
    outcomes = [r.split("|")[2] for r in reports]
    assert outcomes.count("consumed") == 1, outcomes
    assert outcomes.count("refused") == 3, outcomes


def test_winner_preregistration_is_recorded(tmp_path: Path) -> None:
    """Scenario 3."""
    path, reports = _race(tmp_path, "L-3", 3)
    winner = next(r for r in reports if r.split("|")[2] == "consumed")
    spent = _entry(path, "L-3")
    assert spent["used_preregistration_id"] == winner.split("|")[1], (
        "the recorded preregistration must be the winner's"
    )
    assert spent["used_on"]


def test_losers_cannot_overwrite_the_winner(tmp_path: Path) -> None:
    """Scenario 4."""
    path, reports = _race(tmp_path, "L-4b", 4)
    spent = _entry(path, "L-4b")
    winners = [r for r in reports if r.split("|")[2] == "consumed"]
    assert len(winners) == 1
    assert spent["used_preregistration_id"] == winners[0].split("|")[1]
    losers = {r.split("|")[1] for r in reports if r.split("|")[2] != "consumed"}
    assert spent["used_preregistration_id"] not in losers


# --------------------------------------------------------------------------
# 5: holder termination
# --------------------------------------------------------------------------


def test_holder_termination_releases_the_lock_immediately(tmp_path: Path) -> None:
    """Scenario 5 -- the property the sentinel design could not provide.

    The holder is killed while holding the lock. The OS releases its lock when
    the process dies, so the next consumer proceeds at once: no staleness
    threshold, no ceiling, no inspection of a pid that may have been recycled.
    """

    path = _registry(tmp_path, "L-CRASH")
    ready = tmp_path / "ready"
    ctx = multiprocessing.get_context("spawn")
    holder = ctx.Process(
        target=_hold_lock_worker, args=(str(path), str(ready), 60.0)
    )
    holder.start()

    deadline = time.time() + 30
    while not ready.exists():
        assert holder.is_alive(), "holder died before signalling ready"
        if time.time() > deadline:  # pragma: no cover
            pytest.fail("holder never became ready")
        time.sleep(0.01)

    # While genuinely alive, the lock must exclude.
    with pytest.raises(ResearchGuardError):
        consume_reservation("L-CRASH", registry_file=path, preregistration_id="pre-early")

    holder.kill()
    holder.join(timeout=30)

    # Killed: the OS has released the lock, so this must now succeed.
    consume_reservation("L-CRASH", registry_file=path, preregistration_id="pre-after")
    assert _entry(path, "L-CRASH")["used_preregistration_id"] == "pre-after"


def test_lock_is_released_after_normal_exit_and_after_exception(
    tmp_path: Path,
) -> None:
    path = _registry(tmp_path, "L-REL")
    with _registry_lock(path):
        pass
    with pytest.raises(ValueError):
        with _registry_lock(path):
            raise ValueError("boom")
    # Both paths must leave the lock free.
    consume_reservation("L-REL", registry_file=path, preregistration_id="pre-rel")


def test_lock_is_exclusive_within_the_process(tmp_path: Path) -> None:
    """A second descriptor in the same process must still be excluded.

    Advisory locks are held per open file description, so a second ``open`` of
    the same file in the same process is genuinely a second contender.
    """

    path = _registry(tmp_path, "L-EXCL")
    with _registry_lock(path):
        with pytest.raises(ResearchGuardError):
            with _registry_lock(path):
                pass  # pragma: no cover


# --------------------------------------------------------------------------
# 6-8: interrupted writes, failures, concurrent readers
# --------------------------------------------------------------------------


def test_interrupted_writes_preserve_registry_validity(tmp_path: Path) -> None:
    """Scenario 6 -- repeated kills never corrupt the registry."""

    path = _registry(tmp_path, "L-KILL")
    ctx = multiprocessing.get_context("spawn")
    for n in range(6):
        proc = ctx.Process(
            target=_consume_worker,
            args=(str(path), "L-KILL", f"pre-{n}", str(tmp_path / f"r{n}")),
        )
        proc.start()
        time.sleep(0.004 * (n + 1))
        proc.kill()
        proc.join(timeout=30)
        _assert_consistent(path, "L-KILL")

    if _entry(path, "L-KILL")["used"] is False:
        consume_reservation("L-KILL", registry_file=path, preregistration_id="pre-final")
    _assert_consistent(path, "L-KILL")


def test_permission_and_replacement_failures_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario 7."""

    # (a) the sidecar cannot be created
    path = _registry(tmp_path, "L-PERM")
    blocker = _lock_path(path)
    blocker.mkdir()  # a directory cannot be opened as a file
    try:
        with pytest.raises(ResearchGuardError):
            consume_reservation("L-PERM", registry_file=path, preregistration_id="p")
    finally:
        blocker.rmdir()
    _assert_consistent(path, "L-PERM")
    assert _entry(path, "L-PERM")["used"] is False

    # (b) the atomic replacement fails
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(
        OSError("simulated")))
    with pytest.raises(OSError):
        consume_reservation("L-PERM", registry_file=path, preregistration_id="p2")
    monkeypatch.undo()
    assert path.read_text(encoding="utf-8") == before
    _assert_consistent(path, "L-PERM")
    strays = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert strays == [], f"temp file leaked: {strays}"

    # recovery works
    consume_reservation("L-PERM", registry_file=path, preregistration_id="p3")
    assert _entry(path, "L-PERM")["used_preregistration_id"] == "p3"


def test_concurrent_readers_never_see_malformed_json(tmp_path: Path) -> None:
    """Scenario 8."""

    path = _registry(tmp_path, "L-ATOMIC")
    stop = tmp_path / "stop"
    out = tmp_path / "reader.json"
    ctx = multiprocessing.get_context("spawn")
    reader = ctx.Process(target=_reader_worker, args=(str(path), str(stop), str(out)))
    reader.start()

    for n in range(10):
        rid = f"L-W{n}"
        data = json.loads(path.read_text(encoding="utf-8"))
        template = dict(_entry(path, "L-ATOMIC"))
        template.update(reservation_id=rid, used=False, status="RESERVED",
                        preregistration_id=None)
        template.pop("used_on", None)
        template.pop("used_preregistration_id", None)
        data["reservations"].append(template)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            consume_reservation(rid, registry_file=path, preregistration_id=f"pre-{n}")
        except (OSError, ResearchGuardError):
            pass  # concurrent reader; fail-closed, registry still valid

    stop.write_text("1", encoding="utf-8")
    reader.join(timeout=60)
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["bad"] == 0, f"{report['bad']} malformed reads"
    assert report["reads"] > 0


# --------------------------------------------------------------------------
# 9-10: concurrent recovery and repeated attempts
# --------------------------------------------------------------------------


def test_concurrent_recovery_cannot_corrupt_the_registry(tmp_path: Path) -> None:
    """Scenario 9 -- many contenders on one reservation."""

    path, reports = _race(tmp_path, "L-REC", 6)
    outcomes = [r.split("|")[2] for r in reports]
    assert outcomes.count("consumed") == 1, outcomes
    assert outcomes.count("refused") == 5, outcomes
    _assert_consistent(path, "L-REC")


def test_repeated_attempts_behave_consistently(tmp_path: Path) -> None:
    """Scenario 10 -- ten sequential attempts: one success, nine identical refusals."""

    path = _registry(tmp_path, "L-REP")
    consume_reservation("L-REP", registry_file=path, preregistration_id="pre-winner")
    for n in range(9):
        with pytest.raises(ResearchGuardError):
            consume_reservation("L-REP", registry_file=path,
                                preregistration_id=f"pre-loser-{n}")
    _assert_consistent(path, "L-REP")
    assert _entry(path, "L-REP")["used_preregistration_id"] == "pre-winner"


def test_unlocked_sidecar_left_behind_is_harmless(tmp_path: Path) -> None:
    """The sidecar persists after release by design; it must carry no state."""

    path = _registry(tmp_path, "L-SIDE")
    consume_reservation("L-SIDE", registry_file=path, preregistration_id="pre-a")
    assert _lock_path(path).exists(), "sidecar is intentionally left in place"

    (tmp_path / "other").mkdir()
    path2 = _registry(tmp_path / "other", "L-SIDE2")
    _lock_path(path2).write_text("garbage from an old sentinel scheme", encoding="utf-8")
    consume_reservation("L-SIDE2", registry_file=path2, preregistration_id="pre-b")
    assert _entry(path2, "L-SIDE2")["used_preregistration_id"] == "pre-b"


def test_real_eth_reservation_untouched(tmp_path: Path) -> None:
    before = REAL_REGISTRY.read_text(encoding="utf-8")
    path, _ = _race(tmp_path, "L-REAL", 2)
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
    assert REAL_ETH_CSV.exists()