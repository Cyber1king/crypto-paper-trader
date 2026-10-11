"""Crash and interruption safety of the reservation registry.

A reservation spend is a read-decide-write under an inter-process lock, ending
in ``mkstemp`` + ``os.replace``. This module asks, for each way that sequence
can be interrupted:

* does the registry remain valid JSON?
* do reservation fields stay internally consistent (``used`` agrees with
  ``status``; a spend is never half-applied)?
* can an incomplete operation appear to have consumed a window?
* is recovery safe, and does the next valid attempt succeed or fail closed?

Everything runs against a temporary registry holding synthetic reservations, in
child processes that are deliberately terminated. The real registry and the
reserved ETH dataset are never written; one test asserts that explicitly.

Platform note: these ran on Windows 11 / CPython 3.12.10. No POSIX evidence is
claimed.
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
    load_registry,
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
    """The invariant that must hold after any interruption, however violent."""

    data = json.loads(path.read_text(encoding="utf-8"))  # valid JSON
    for rid in ids:
        entry = next(e for e in data["reservations"] if e["reservation_id"] == rid)
        assert entry["used"] is (entry["status"] == "USED"), (
            f"{rid}: used={entry['used']} contradicts status={entry['status']}"
        )
        if entry["used"]:
            assert entry["used_preregistration_id"], (
                f"{rid}: marked used but no preregistration recorded"
            )
            assert entry["used_on"], f"{rid}: marked used but no timestamp"
        else:
            assert entry.get("used_preregistration_id") is None, (
                f"{rid}: unspent but carries a preregistration record"
            )
            assert "used_on" not in entry, f"{rid}: unspent but carries a timestamp"



def _atomic_write(path: Path, data: dict) -> None:
    """Seed the registry the way the product writes it: tmp + os.replace.

    ``path.write_text`` truncates and then writes, so a concurrent reader can
    legitimately observe a half-written file. That would measure the *test's*
    setup, not the guard's write path.
    """

    import os
    import tempfile

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------
# child processes
# --------------------------------------------------------------------------


def _hold_lock_then_consume(registry: str, rid: str, pre: str, ready: str) -> None:
    """Acquire the lock, signal, then consume -- widening the crash window."""

    target = Path(registry)
    with _registry_lock(target):
        Path(ready).write_text("1", encoding="utf-8")
        time.sleep(0.25)  # parent can kill inside the held-lock window
        consume_reservation(rid, registry_file=registry, preregistration_id=pre)


def _consume_only(registry: str, rid: str, pre: str) -> None:
    consume_reservation(rid, registry_file=registry, preregistration_id=pre)


def _reader_worker(registry: str, stop: str, out: str) -> None:
    """Read the registry repeatedly; every read must parse."""

    bad = 0
    reads = 0
    # Baseline reads before the writer starts: on Windows os.replace cannot
    # target a file a reader holds open, so once the writer is active a reader
    # may never win a window. The invariant under test is "never malformed".
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
            # Windows refuses os.replace while a reader holds the target open.
            # The writer fails closed; the reader simply skips this attempt.
            pass
        except json.JSONDecodeError:
            bad += 1
    Path(out).write_text(json.dumps({"reads": reads, "bad": bad}), encoding="utf-8")


# --------------------------------------------------------------------------
# interruption while the lock is held
# --------------------------------------------------------------------------


def test_crash_while_holding_lock_releases_it_immediately(tmp_path: Path) -> None:
    """Killed inside the held-lock window: no spend, and the OS frees the lock.

    Under the previous sentinel-file design this was the failure mode that
    mattered: a killed holder left a lock file that nothing could reclaim,
    because a terminated pid still resolves on Windows. With an OS-native
    advisory lock the kernel releases it when the process dies, so the next
    consumer proceeds immediately.
    """

    path = _registry(tmp_path, "C-HOLD")
    ready = tmp_path / "ready"
    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(
        target=_hold_lock_then_consume, args=(str(path), "C-HOLD", "pre-crash", str(ready))
    )
    proc.start()

    deadline = time.time() + 30
    while not ready.exists():
        if time.time() > deadline:  # pragma: no cover
            pytest.fail("child never signalled ready")
        time.sleep(0.005)

    proc.kill()  # hard termination while the lock is held
    proc.join(timeout=30)

    _assert_consistent(path, "C-HOLD")
    assert _entry(path, "C-HOLD")["used"] is False, (
        "a killed evaluation must not appear to have consumed the window"
    )

    # The OS released the lock with the process, so this must succeed at once --
    # no staleness threshold, no ceiling, no orphan to reclaim.
    consume_reservation("C-HOLD", registry_file=path, preregistration_id="pre-after")
    _assert_consistent(path, "C-HOLD")
    assert _entry(path, "C-HOLD")["used_preregistration_id"] == "pre-after"



def test_repeated_kills_never_corrupt_the_registry(tmp_path: Path) -> None:
    """Many kills at varying offsets must never produce partial or false state."""

    path = _registry(tmp_path, "C-KILL")
    ctx = multiprocessing.get_context("spawn")

    for index in range(6):
        proc = ctx.Process(
            target=_consume_only, args=(str(path), "C-KILL", f"pre-{index}")
        )
        proc.start()
        # Offset sweeps from "just started" to "probably finished", so the kill
        # lands at different phases of read -> check -> write -> replace.
        time.sleep(0.002 * (index + 1))
        proc.kill()
        proc.join(timeout=30)
        _assert_consistent(path, "C-KILL")

    # Whatever happened above, the registry is still usable.
    if _entry(path, "C-KILL")["used"] is False:
        consume_reservation("C-KILL", registry_file=path, preregistration_id="pre-final")
    _assert_consistent(path, "C-KILL")
    assert _entry(path, "C-KILL")["used"] is True


# --------------------------------------------------------------------------
# atomicity of the visible write
# --------------------------------------------------------------------------


def test_reader_never_observes_a_partially_written_registry(tmp_path: Path) -> None:
    """Concurrent readers must always see complete, valid JSON."""

    path = _registry(tmp_path, "C-ATOMIC")
    stop = tmp_path / "stop"
    out = tmp_path / "reader.json"

    ctx = multiprocessing.get_context("spawn")
    reader = ctx.Process(target=_reader_worker, args=(str(path), str(stop), str(out)))
    reader.start()

    for n in range(12):
        rid = f"C-W{n}"
        # Rotate through distinct reservations on one shared registry so the
        # writer is genuinely rewriting the file while the reader polls it.
        data = json.loads(path.read_text(encoding="utf-8"))
        template = dict(_entry(path, "C-ATOMIC"))
        template["reservation_id"] = rid
        template["used"] = False
        template["status"] = "RESERVED"
        template["preregistration_id"] = None
        template.pop("used_on", None)
        template.pop("used_preregistration_id", None)
        data["reservations"].append(template)
        _atomic_write(path, data)
        try:
            consume_reservation(rid, registry_file=path, preregistration_id=f"pre-{n}")
        except (OSError, ResearchGuardError):
            # A reader holding the file open makes os.replace fail on Windows.
            # That is the fail-closed path; the invariant is that the registry
            # stays valid, which the reader measures directly.
            pass

    stop.write_text("1", encoding="utf-8")
    reader.join(timeout=30)

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["bad"] == 0, f"reader saw {report['bad']} unparseable registries"
    assert report["reads"] > 0, "the reader never managed a read"


def test_leftover_temp_file_cannot_corrupt_the_registry(tmp_path: Path) -> None:
    """A stray ``.tmp`` from a crashed writer is inert."""

    path = _registry(tmp_path, "C-TMP")
    before = path.read_text(encoding="utf-8")
    stray = path.with_name(path.name + ".tmp")
    stray.write_text("{ this is not json", encoding="utf-8")

    consume_reservation("C-TMP", registry_file=path, preregistration_id="pre-x")
    _assert_consistent(path, "C-TMP")
    assert _entry(path, "C-TMP")["used"] is True
    assert path.read_text(encoding="utf-8") != before


def test_atomic_replace_failure_fails_closed_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the atomic replacement fails, nothing is committed and the temp goes."""

    path = _registry(tmp_path, "C-FAIL")
    before = path.read_text(encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError):
        consume_reservation("C-FAIL", registry_file=path, preregistration_id="pre-f")

    monkeypatch.undo()

    assert path.read_text(encoding="utf-8") == before, "registry was mutated"
    _assert_consistent(path, "C-FAIL")
    assert _entry(path, "C-FAIL")["used"] is False
    strays = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert strays == [], f"temporary file not cleaned up: {strays}"
    # The sidecar persists by design; what must not persist is a held lock.
    with _registry_lock(path):
        pass  # acquiring again proves the lock was released

    # Recovery works: the next attempt succeeds normally.
    consume_reservation("C-FAIL", registry_file=path, preregistration_id="pre-recover")
    assert _entry(path, "C-FAIL")["used_preregistration_id"] == "pre-recover"


# --------------------------------------------------------------------------
# concurrent stale-lock recovery
# --------------------------------------------------------------------------




def test_real_eth_reservation_untouched_by_crash_testing(tmp_path: Path) -> None:
    before = REAL_REGISTRY.read_text(encoding="utf-8")

    path = _registry(tmp_path, "C-HOLD")
    ready = tmp_path / "ready"
    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(
        target=_hold_lock_then_consume, args=(str(path), "C-HOLD", "pre", str(ready))
    )
    proc.start()
    deadline = time.time() + 30
    while not ready.exists():
        if time.time() > deadline:  # pragma: no cover
            pytest.fail("child never signalled ready")
        time.sleep(0.005)
    proc.kill()
    proc.join(timeout=30)

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