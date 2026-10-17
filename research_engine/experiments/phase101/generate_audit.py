"""Generate the Phase 101 exclusion audit by static analysis only.

Runs no test. Reads every ``tests/test_*.py``, builds the transitive call graph
over local helpers, and records which test functions can reach a prohibited
evaluation entry point.

The per-file reserved-ETH flag is computed inside the file loop and stored on
each record. An earlier version read it after the loop, so every record
inherited the last file's value and reported zero reserved-ETH exposure --
falsely clearing a safety-relevant finding. The test suite now pins this.
"""
from __future__ import annotations

import ast
import collections
import json
import pathlib

EVAL = {
    "run_backtest": "engine.run_backtest",
    "walk_forward": "engine.walk_forward",
    "run_experiment": "engine.run_experiment",
    "run_yearly_backtests": "engine.run_yearly_backtests",
    "analyze": "engine.analyze",
    "realised_volatility": "engine.realised_volatility",
    "mark_to_market_drawdown": "engine.mark_to_market_drawdown",
    "Replay": "engine.Replay",
}

#: Bare call names, mapped to the forbidden entry point they really are.
_NAMESPACE = {".step": "engine.Replay.step"}


def analyse(path: pathlib.Path) -> list[dict]:
    src = path.read_text(encoding="utf-8")
    # Per FILE, captured before the loop body mutates anything.
    reserved = ("phase33" in src) or ("ETHUSDT" in src)
    tree = ast.parse(src)
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    info: dict[str, set[str]] = {k: set() for k in funcs}
    for name, node in funcs.items():
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                fn = call.func
                called = (
                    fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                )
                if called in EVAL:
                    info[name].add(called)
                elif called == "step":
                    info[name].add(".step")

    changed = True
    while changed:
        changed = False
        for name, node in funcs.items():
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                    other = call.func.id
                    if other in info:
                        extra = info[other] - info[name]
                        if extra:
                            info[name] |= extra
                            changed = True

    records: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    records.extend(_record(path, f"{path.stem}::{node.name}::{item.name}", item.name, info, reserved))
        elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            records.extend(_record(path, f"{path.stem}::{node.name}", node.name, info, reserved))
    return records


def _record(path, node_id, test_name, info, reserved) -> list[dict]:
    if not info[test_name]:
        return []
    return [{
        "node_id": node_id,
        "file": path.stem,
        "test": test_name,
        "class_name": node_id.split("::")[1] if node_id.count("::") == 2 else None,
        "entry_points": sorted(EVAL.get(h, _NAMESPACE.get(h, h)) for h in info[test_name]),
        "calls_prohibited_operation": True,
        "data_source": "reserved_eth" if reserved else "frozen_btc_or_synthetic",
        "touches_reserved_eth": reserved,
        "disposition": "EXCLUDED",
        "reason": "invokes prohibited evaluation path"
        + (" and touches the reserved ETH dataset" if reserved else ""),
        "safe_alternative": "covered by safe surface tests where a contract exists",
    }]


def main() -> dict:
    entries: list[dict] = []
    for path in sorted(pathlib.Path("tests").glob("test_*.py")):
        entries.extend(analyse(path))

    ids = [r["node_id"] for r in entries]
    dupes = [i for i, c in collections.Counter(ids).items() if c > 1]
    artifact = {
        "generated_for": "Master Batch 99-102 / Phase 101",
        "method": "static transitive call-graph analysis over tests/*.py; no test executed",
        "forbidden_entry_points": sorted(set(EVAL.values()) | set(_NAMESPACE.values())),
        "counts": {
            "evaluation_touching_node_ids": len(entries),
            "unique_node_ids": len(set(ids)),
            "duplicate_node_ids": dupes,
            "touches_reserved_eth": sum(1 for r in entries if r["touches_reserved_eth"]),
            "reconciliation": (
                "the earlier 152 and 579 figures came from narrower file sets; "
                "this enumerates ALL test files and supersedes both"
            ),
        },
        "by_file": dict(sorted(collections.Counter(r["file"] for r in entries).items())),
        "tests": entries,
    }
    out = pathlib.Path("experiments/phase101")
    out.mkdir(parents=True, exist_ok=True)
    (out / "excluded_test_audit.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    art = main()
    print("records:", art["counts"]["evaluation_touching_node_ids"],
          "unique:", art["counts"]["unique_node_ids"],
          "reserved_eth:", art["counts"]["touches_reserved_eth"])
