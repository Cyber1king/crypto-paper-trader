#!/usr/bin/env python
"""Fail-closed gate for running research-engine tests.

Why this exists
---------------
One session ran ``tests/test_replay.py``, which carries 154 records in the
reserved-evaluation exclusion audit, because the exclusion list was consulted
for every file in a loop except the one reached for last. Another session
triggered whole-tree collection because a file list resolved to nothing and an
empty argument silently expanded into discovery. Both share one cause: no gate.

Process exit-code contract
--------------------------
Gate-owned codes occupy the disjoint range 120-126. Within 0-5 only pytest's
own result is ever returned, so a gate condition can never be confused with a
test outcome.

  0        clean success: either a --dry-run that validated, or pytest
           returned 0. Every audit record was persisted and verified.
  1..5     pytest's own exit code, passed through unchanged
           (1 tests failed, 2 interrupted, 3 internal error, 4 usage error,
           5 no tests collected). Every audit record was persisted.
  120      POLICY REFUSAL. A validation rule refused the run - unapproved,
           blocked, excluded, malformed or non-existent target; empty target
           list; invalid deselection. No test process was created. A REFUSED
           record is written when the log is writable.
  121      CONFIGURATION / INTEGRITY ERROR, OR LAUNCH FAILURE. The allowlist,
           audit or log could not be trusted, or the test process could not be
           started at all. No test process was created.
  126      EXECUTION OCCURRED but the final record could not be persisted.
           126 is a GATE LOGGING FAILURE and is not a pytest result. The real
           pytest return code is printed on stdout as ``PYTEST_EXIT_CODE=<n>``
           and is embedded in the stderr message.

  (2 is additionally argparse's usage-error code for a malformed command line.
   The gate itself never returns 2. argparse exits during argument parsing,
   before any repository path is resolved and before any subprocess of any kind
   exists, so a malformed command line can never reach a test process.)

Every gate-owned category maps to exactly one code, and every one of those
codes lies outside pytest's 0-5 range.

Design rules
------------
1. Permission comes ONLY from an explicit entry in ``test_allowlist.json``.
   Directory membership, filename similarity, and "not on the denylist" are
   never permission.
2. An empty target list is refused, never treated as "run everything".
3. Targets are resolved to explicit file paths before any subprocess exists.
   pytest is never handed a directory and never handed an empty argument.
4. Every refusal path exits non-zero. There is no degraded mode.
5. Subprocess ordering is exactly:
      (a) validation - pure filesystem and text work, no subprocess
      (b) ``git rev-parse HEAD`` - read-only Git metadata, spawned AFTER
          validation succeeds and BEFORE the pre-run record. It exists only to
          stamp the audit record. It is not a test process and cannot run one.
          If it fails, the gate refuses; it never proceeds with an unknown
          repository identity.
      (c) pre-run record written AND read back
      (d) pytest
6. The allowlist digest is re-verified immediately before (c). If the file
   changed during validation, the gate refuses rather than logging a stale
   plan.
7. If the final record cannot be written after (d), the outcome is reported as
   126 with the real pytest code, and is never described as though nothing ran.

Concurrency and integrity limitations - stated, not papered over
---------------------------------------------------------------
* ``O_APPEND`` makes a write an append, but atomicity ACROSS PROCESSES is NOT
  guaranteed on Windows and is guaranteed on POSIX only for writes below
  PIPE_BUF. This gate does not claim race-freedom.
* Each write is read back and compared. If another writer interleaved, the
  comparison fails and the gate REFUSES. Concurrent invocations therefore
  produce spurious refusals rather than a corrupt log. That is deliberate.
* Every existing non-empty log line is parsed before appending. One malformed
  line anywhere makes the log untrusted and the gate refuses to append.
* Time-of-check/time-of-use: the allowlist, audit and log are read during
  validation and the allowlist digest is re-checked before the pre-run write,
  but a replacement in the remaining window is not detectable. This is a
  residual limitation of any filesystem-based check, not a guarantee.

This module has never been executed. Its behaviour is established by reading,
not by running.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import FrozenSet

#: Exit codes. Gate-owned codes live in a disjoint range (120-126) so they can
#: never collide with pytest's own codes (0-5) or with argparse's usage error.
#: Within 0-5, only pytest's actual result is ever returned.
USAGE_ERROR = 2          # argparse only; never returned by the gate itself
POLICY_REFUSAL = 120     # a validation rule refused the run
CONFIG_ERROR = 121       # configuration, audit or log integrity; or launch failure
FINAL_LOG_FAILED = 126   # pytest ran, but the final record was not persisted
RECONCILED = 129         # an orphaned STARTED was closed by AUDIT_INCOMPLETE; no test ran
INTERRUPTED = 130        # a test process was created but its outcome is unknown
TIMED_OUT = 131          # a test process was created and killed on timeout; outcome unknown

#: Conservative default wall-clock limit for one pytest process. Long enough for
#: a slow allowlisted file on a loaded machine, short enough that a genuinely
#: hung process cannot hold an audit record open indefinitely. A timeout is
#: recorded as TIMEOUT, which asserts an unknown outcome - never as a pytest
#: result. Override with --timeout-seconds; 0 explicitly disables the limit and
#: is itself recorded in the STARTED record.
DEFAULT_TEST_TIMEOUT_SECONDS = 1800

# Backwards-compatible alias for the policy-refusal code.
REFUSED = POLICY_REFUSAL

REQUIRED_ALLOWLIST_KEYS = (
    "schema_version",
    "generated_from",
    "test_root",
    "allowed_files",
    "allowed_node_ids",
    "blocked_pending_review",
    "explicitly_denied_files",
    "explicitly_denied_node_ids",
)

REQUIRED_AUDIT_KEYS = ("tests", "counts", "forbidden_entry_points")
REQUIRED_AUDIT_RECORD_KEYS = ("node_id", "file", "touches_reserved_eth")

#: Every status this gate is capable of writing. A record carrying anything else
#: was not produced by this gate, or was edited by hand; either way the history
#: cannot be interpreted and the log is refused rather than extended.
KNOWN_STATUSES = frozenset(
    {
        "REFUSED",
        "REFUSED_CONFIG",
        "REFUSED_NO_CONTEXT",
        "DRY_RUN",
        "STARTED",
        "FINISHED",
        "LAUNCH_FAILED",
        "AUDIT_INCOMPLETE",
        "INTERRUPTED",
        "TIMEOUT",
    }
)

#: The only statuses that may follow an open ``STARTED``. A run that is opened
#: and never closed by one of these left test state unknown, so the gate refuses
#: to start another run until a human resolves it.
#:
#: ``INTERRUPTED`` and ``TIMEOUT`` mean the test process WAS created but its final
#: outcome could not be established. They are deliberately distinct from
#: ``LAUNCH_FAILED``, which asserts that no test process was ever created.
RUN_TERMINAL_STATUSES = frozenset(
    {"FINISHED", "LAUNCH_FAILED", "AUDIT_INCOMPLETE", "INTERRUPTED", "TIMEOUT"}
)

#: The only statuses that mean a test process actually ran AND its result was
#: recorded. This is deliberately NOT the same set as ``RUN_TERMINAL_STATUSES``:
#: "closes a run" and "run succeeded" are different facts.
#:
#: ``AUDIT_INCOMPLETE`` closes a run without ever asserting a test result. It is
#: the record of a run whose execution outcome the gate failed to capture, so it
#: can never appear here.
SUCCESS_STATUSES = frozenset({"FINISHED"})

#: Invariant, checked at import. If a future edit ever made an audit-repair
#: status "successful", this raises at import rather than silently misreporting.
_AUDIT_INCOMPLETE = "AUDIT_INCOMPLETE"
if _AUDIT_INCOMPLETE in SUCCESS_STATUSES:
    raise RuntimeError(
        "AUDIT_INCOMPLETE must never be a success status: it records an "
        "incomplete audit and asserts nothing about the test outcome"
    )
if _AUDIT_INCOMPLETE not in RUN_TERMINAL_STATUSES:
    raise RuntimeError(
        "AUDIT_INCOMPLETE must be run-terminal, or an orphan could never be "
        "closed without rewriting history"
    )
if _AUDIT_INCOMPLETE not in KNOWN_STATUSES:
    raise RuntimeError(
        "AUDIT_INCOMPLETE must be a known status, or its own records would be "
        "rejected as uninterpretable history"
    )

#: Same invariant for the two outcomes a human cannot verify. Neither may ever
#: be reported as a test success: each says a process was created and the result
#: is UNKNOWN.
for _unknown_outcome in ("INTERRUPTED", "TIMEOUT"):
    if _unknown_outcome in SUCCESS_STATUSES:
        raise RuntimeError(
            f"{_unknown_outcome} asserts an unknown outcome and must never be a "
            "success status"
        )
    if _unknown_outcome not in RUN_TERMINAL_STATUSES:
        raise RuntimeError(
            f"{_unknown_outcome} must be run-terminal, or its run could never "
            "be closed without rewriting history"
        )
    if _unknown_outcome not in KNOWN_STATUSES:
        raise RuntimeError(
            f"{_unknown_outcome} must be a known status, or its own records "
            "would be rejected as uninterpretable history"
        )

#: Conservative node-identifier alphabet: letters, digits, underscore, hyphen,
#: dot, and the bracket pair used for pytest parametrisation. Spaces, quotes,
#: equals signs, commas and path separators are refused rather than escaped.
NODE_ALPHABET = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "_-.[]"
)


class Refusal(Exception):
    """A validation rule failed. Not recoverable by retrying."""


class ConfigError(Exception):
    """Configuration, audit or log integrity could not be established."""


@dataclass(frozen=True)
class Context:
    """Every path the gate uses, derived from ONE resolved repository root."""

    repo_root: Path
    test_root: Path
    allowlist_path: Path
    audit_path: Path
    log_path: Path
    allowed_files: FrozenSet[str]
    allowed_nodes: FrozenSet[str]
    blocked_files: FrozenSet[str]
    denied_files: FrozenSet[str]
    denied_nodes: FrozenSet[str]
    excluded_files: FrozenSet[str]
    excluded_nodes: FrozenSet[str]
    allowlist_digest: str
    audit_digest: str
    gate_digest: str
    audit_record_count: int


def fail(message: str, code: int = REFUSED) -> int:
    print(f"REFUSED: {message}", file=sys.stderr)
    return code


def load_json(path: Path, label: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"{label} could not be read ({path}): {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{label} is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{label} must contain a JSON object ({path})")
    return data


def require_str_list(config: dict, key: str, source: str) -> list[str]:
    value = config.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"{source} key {key!r} must be a list")
    if any(not isinstance(v, str) or not v for v in value):
        raise ConfigError(f"{source} key {key!r} must contain non-empty strings only")
    return value


def is_safe_relative(rel: str) -> bool:
    """True only for a plain relative path under the test root.

    Permitted characters per segment: ``[A-Za-z0-9_.-]``. The dot is required
    because every approvable target is a ``.py`` file, and its extension lives
    in the segment.

    Allowing the dot as a CHARACTER does not weaken the traversal guard: the
    check for segments exactly equal to ``.`` or ``..`` runs first and is
    unaffected by this character set. ``tests/../secret.py`` splits into a
    ``".."`` segment and is refused before this character test is reached.

    Also rejects absolute paths, drive letters, UNC prefixes, and empty
    segments.
    """

    if not rel or rel != rel.strip():
        return False
    if rel.startswith(("/", "\\")):
        return False
    if ":" in rel:
        return False
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return False
    return all(
        part.isascii() and all(c.isalnum() or c in "_-." for c in part)
        for part in parts
    )


def is_safe_node(node: str) -> bool:
    """True only for a conservative pytest node identifier.

    Deliberately narrow. A node id that needs an exotic character is refused
    rather than quoted or escaped, because the gate never needs to accept one.
    """

    if not node:
        return False
    return all(c in NODE_ALPHABET for c in node)


def parse_target(raw: str) -> tuple[str, str | None]:
    """Split a target into (relative test path, node id or None)."""

    if "::" in raw:
        rel, _, node = raw.partition("::")
        if not is_safe_relative(rel) or not rel.endswith(".py"):
            raise Refusal(f"malformed node target {raw!r}")
        if not is_safe_node(node):
            raise Refusal(
                f"node in {raw!r} uses characters outside the permitted set; "
                "refusing rather than escaping it"
            )
        return rel, raw
    if not is_safe_relative(raw) or not raw.endswith(".py"):
        raise Refusal(
            f"malformed target {raw!r}; expected a plain relative path ending .py"
        )
    return raw, None


def resolve_existing_file(ctx: Context, rel: str, label: str) -> Path:
    """Resolve ``rel`` under the test root and verify containment and file-ness.

    Refuses traversal, absolute paths, directories, symlinks at any level
    between the test root and the file, and anything canonicalising outside the
    test root.
    """

    candidate = ctx.test_root / rel
    candidate = candidate.resolve()

    root = ctx.test_root.resolve()
    if root != candidate and root not in candidate.parents:
        raise Refusal(
            f"{label} {rel!r} resolves outside the configured test root "
            f"({root}); refusing"
        )

    walk = root
    for part in Path(rel).parts:
        walk = walk / part
        if walk.is_symlink():
            raise Refusal(f"{label} {rel!r} traverses a symlink at {walk}; refusing")

    if not candidate.is_file():
        raise Refusal(f"{label} {rel!r} does not exist as a regular file")

    return candidate


def validate_target(ctx: Context, raw: str) -> str:
    rel, node = parse_target(raw)

    if rel in ctx.denied_files:
        raise Refusal(f"{rel} is explicitly denied by the allowlist")
    if node is not None and node in ctx.denied_nodes:
        raise Refusal(f"node {node!r} is explicitly denied by the allowlist")
    if rel in ctx.blocked_files:
        raise Refusal(
            f"{rel} is BLOCKED pending manual isolation review; it is not "
            "approved for execution"
        )
    if rel not in ctx.allowed_files:
        raise Refusal(
            f"{rel} is not in the allowlist; add it deliberately after review"
        )
    if node is not None and node not in ctx.allowed_nodes:
        raise Refusal(
            f"node {node!r} is not individually approved; the file is approved, "
            "this node is not"
        )
    if rel in ctx.excluded_files:
        raise Refusal(
            f"{rel} has reserved-evaluation records in the exclusion audit and "
            "must not be executed"
        )
    if node is not None and node in ctx.excluded_nodes:
        raise Refusal(f"node {node!r} has a reserved-evaluation record")

    resolve_existing_file(ctx, rel, "target")
    return rel


def validate_deselect(ctx: Context, raw: str) -> str:
    if "::" not in raw:
        raise Refusal(
            f"malformed --deselect {raw!r}; expected 'relative/path.py::<node>'"
        )
    rel, _node = parse_target(raw)
    if rel not in ctx.allowed_files:
        raise Refusal(
            f"--deselect names {rel}, which is not approved; a deselect may "
            "never authorise an unapproved test"
        )
    if rel in ctx.excluded_files or rel in ctx.blocked_files:
        raise Refusal(f"--deselect names {rel}, which may not be run at all")
    resolve_existing_file(ctx, rel, "deselect")
    return raw


def load_audit(repo_root: Path, rel_audit: str) -> tuple[FrozenSet[str], FrozenSet[str], int]:
    """Load and structurally validate the exclusion audit. Fails closed.

    Provenance limitation: the audit carries no embedded checksum and none can
    be added without changing the generator that produces it. This gate
    therefore verifies STRUCTURE and INTERNAL CONSISTENCY, not provenance or
    freshness. A regenerated but well-formed audit would be accepted. That is
    stated rather than concealed behind an invented checksum.
    """

    path = repo_root / rel_audit
    data = load_json(path, "exclusion audit")

    for key in REQUIRED_AUDIT_KEYS:
        if key not in data:
            raise ConfigError(f"exclusion audit is missing required key {key!r}")

    tests = data["tests"]
    if not isinstance(tests, list) or not tests:
        raise ConfigError("exclusion audit has an empty or non-list 'tests'")

    counts = data["counts"]
    if not isinstance(counts, dict):
        raise ConfigError("exclusion audit 'counts' must be an object")
    declared = counts.get("evaluation_touching_node_ids")
    if not isinstance(declared, int) or declared <= 0:
        raise ConfigError(
            "exclusion audit 'counts.evaluation_touching_node_ids' must be a "
            "positive integer; refusing an audit that cannot state its size"
        )
    if declared != len(tests):
        raise ConfigError(
            f"exclusion audit is internally inconsistent: counts say "
            f"{declared} records, 'tests' holds {len(tests)}"
        )

    files: set[str] = set()
    nodes: set[str] = set()
    for index, record in enumerate(tests):
        if not isinstance(record, dict):
            raise ConfigError(f"exclusion audit record {index} is not an object")
        for key in REQUIRED_AUDIT_RECORD_KEYS:
            if key not in record:
                raise ConfigError(
                    f"exclusion audit record {index} is missing {key!r}"
                )
        raw_file = record["file"]
        node_id = record["node_id"]
        if not isinstance(raw_file, str) or not raw_file:
            raise ConfigError(f"exclusion audit record {index} has a bad 'file'")
        if not isinstance(node_id, str) or not node_id:
            raise ConfigError(f"exclusion audit record {index} has a bad 'node_id'")
        if raw_file.endswith(".py"):
            raise ConfigError(
                f"exclusion audit record {index} names {raw_file!r}; the 'file' "
                "field is expected without a .py suffix"
            )
        files.add(f"tests/{raw_file}.py")
        nodes.add(f"tests/{raw_file}.py::{node_id}")

    return frozenset(files), frozenset(nodes), len(tests)


def digest_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ConfigError(f"{path} could not be digested: {exc}") from exc


def gate_source_digest() -> str:
    """SHA-256 of this gate's own bytes on disk.

    Computed from the file exactly as the interpreter loaded it, so the value
    identifies the source that is actually running rather than a reconstructed
    or normalised copy. A failure here is fatal: without it a record could not
    be tied to a gate version, so the caller refuses rather than proceeding.
    """

    try:
        return digest_file(Path(__file__).resolve())
    except ConfigError as exc:
        raise ConfigError(f"gate source could not be digested: {exc}") from exc


def build_context(repo_root_arg: str) -> Context:
    repo_root = Path(repo_root_arg).expanduser().resolve()
    if not repo_root.is_dir():
        raise ConfigError(f"repository root is not a directory: {repo_root}")

    tools_dir = repo_root / "tools"
    allowlist_path = tools_dir / "test_allowlist.json"
    config = load_json(allowlist_path, "test allowlist")

    for key in REQUIRED_ALLOWLIST_KEYS:
        if key not in config:
            raise ConfigError(f"test allowlist is missing required key {key!r}")
    if config["schema_version"] != "safe-test-allowlist/1":
        raise ConfigError(
            f"unsupported allowlist schema_version "
            f"{config['schema_version']!r}; refusing"
        )

    test_root_raw = config["test_root"]
    if not isinstance(test_root_raw, str) or not is_safe_relative(test_root_raw):
        raise ConfigError("allowlist 'test_root' is not a simple relative path")
    test_root = repo_root / test_root_raw
    if not test_root.is_dir():
        raise ConfigError(f"configured test_root is not a directory: {test_root}")

    audit_path = repo_root / config["generated_from"]
    excluded_files, excluded_nodes, record_count = load_audit(
        repo_root, config["generated_from"]
    )
    # Digested AFTER load_audit succeeds, so the digest can only ever describe an
    # audit that has already been parsed and found structurally valid.
    audit_digest = digest_file(audit_path)

    allowed = frozenset(require_str_list(config, "allowed_files", "allowlist"))
    if not allowed:
        raise ConfigError("allowlist approves no files; refusing")

    overlap = allowed & excluded_files
    if overlap:
        raise ConfigError(
            "allowlist approves files that the exclusion audit forbids: "
            + ", ".join(sorted(overlap))
        )
    blocked = frozenset(require_str_list(config, "blocked_pending_review", "allowlist"))
    overlap = blocked & excluded_files
    if overlap:
        raise ConfigError(
            "allowlist blocks files the audit also forbids; that is safe but "
            "redundant: " + ", ".join(sorted(overlap))
        )

    return Context(
        repo_root=repo_root,
        test_root=test_root,
        allowlist_path=allowlist_path,
        audit_path=audit_path,
        log_path=tools_dir / "execution_log.jsonl",
        allowed_files=allowed,
        allowed_nodes=frozenset(
            require_str_list(config, "allowed_node_ids", "allowlist")
        ),
        blocked_files=blocked,
        denied_files=frozenset(
            require_str_list(config, "explicitly_denied_files", "allowlist")
        ),
        denied_nodes=frozenset(
            require_str_list(config, "explicitly_denied_node_ids", "allowlist")
        ),
        excluded_files=excluded_files,
        excluded_nodes=excluded_nodes,
        allowlist_digest=digest_file(allowlist_path),
        audit_digest=audit_digest,
        gate_digest=gate_source_digest(),
        audit_record_count=record_count,
    )


def _require_wellformed_digest(value: object, field: str, index: int) -> None:
    """Raise unless ``value`` is a 64-char lowercase hex SHA-256 string."""

    if not isinstance(value, str):
        raise ConfigError(
            f"execution log line {index} has a non-string {field}"
        )
    if not (len(value) == 64 and all(c in "0123456789abcdef" for c in value)):
        raise ConfigError(
            f"execution log line {index} has a malformed {field}; "
            "refusing to append to a log whose provenance is unclear"
        )


def log_is_intact(log_path: Path) -> int | None:
    """Validate EVERY non-empty line of an existing log before appending.

    Cross-process atomicity of O_APPEND is not claimed. What is verified is
    that the file currently parses in full and that its history is interpretable:
    every status is a known one, no record is truncated, and no record
    interrupts a run that is still open. If any of that fails the audit trail is
    already untrustworthy and appending would compound the damage.

    Returns the line number of a ``STARTED`` still open at end-of-log, else None.
    An open run is deliberately NOT an error here: the very next append may be the
    terminal record that closes it, and refusing on sight would make closing a run
    impossible. ``append_record`` decides what an open run means for the record it
    is about to write.
    """

    if not log_path.exists():
        return
    try:
        raw = log_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(
            f"execution log exists but could not be read cleanly ({log_path}): "
            f"{exc}; refusing to append"
        ) from exc
    # Every record this gate writes ends with a newline. A non-empty log whose
    # last line does not is the signature of a process killed mid-append, which
    # leaves the final record ambiguous.
    if raw and not raw.endswith("\n"):
        raise ConfigError(
            "execution log does not end with a newline; its final record may be "
            "truncated by an interrupted write, so the history is ambiguous. "
            "Refusing to append until it is resolved by hand"
        )
    open_run: int | None = None
    for index, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"execution log line {index} is malformed ({exc}); the audit "
                "trail cannot be trusted and appending would compound it"
            ) from exc
        if not isinstance(parsed, dict) or "status" not in parsed or "timestamp_utc" not in parsed:
            raise ConfigError(
                f"execution log line {index} is not a gate record; refusing to "
                "append to a log of unknown provenance"
            )
        status = parsed["status"]
        if status not in KNOWN_STATUSES:
            raise ConfigError(
                f"execution log line {index} has unrecognised status {status!r}; "
                "refusing to append to a log whose history cannot be interpreted"
            )
        # Lifecycle tracking. A STARTED opens a run; only a terminal status may
        # close it. Nothing here rewrites or removes a record -- an unresolved
        # run is reported and the append refused.
        if open_run is None:
            if status == "STARTED":
                open_run = index
        elif status not in RUN_TERMINAL_STATUSES:
            raise ConfigError(
                f"execution log line {index} has status {status!r} while the run "
                f"opened at line {open_run} is unresolved; refusing to append "
                "until that run is resolved by hand"
            )
        else:
            open_run = None
        # ``gate_sha256`` and ``audit_sha256`` are validated only when present.
        # Records written before a field existed are historical and must not be
        # rewritten or rejected; a record that DOES carry the field must carry a
        # well-formed digest.
        for field in ("gate_sha256", "audit_sha256"):
            if field in parsed:
                _require_wellformed_digest(parsed[field], field, index)
        if "target_sha256" in parsed:
            mapping = parsed["target_sha256"]
            if not isinstance(mapping, dict):
                raise ConfigError(
                    f"execution log line {index} has a non-object target_sha256"
                )
            for rel, value in mapping.items():
                _require_wellformed_digest(value, f"target_sha256[{rel!r}]", index)
    return open_run


@contextlib.contextmanager
def log_write_lock(log_path: Path):
    """Hold an exclusive advisory lock across one log append.

    Windows uses ``msvcrt.locking``; POSIX uses ``fcntl.flock``. Both are in the
    standard library, so no dependency is introduced. The lock is taken on a
    SIDECAR file rather than the log itself: locking the log would conflict with
    the ``O_APPEND`` writes this gate performs, and the log may not exist yet.

    The lock is advisory and cooperative. It prevents two GATE processes from
    interleaving an append; it cannot prevent a non-cooperating writer. That is
    why the post-write read-back in :func:`append_record` is retained: the lock
    narrows the window, the read-back is what detects a violation.

    The lock is released in a ``finally``, so an ordinary error, a
    ``KeyboardInterrupt`` or any other exception cannot strand it.
    """

    lock_path = log_path.with_name(log_path.name + ".lock")
    try:
        fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
    except OSError as exc:
        raise ConfigError(
            f"could not open the log lock file {lock_path}: {exc}"
        ) from exc
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ConfigError(
                    "another gate process holds the execution-log lock; refusing "
                    f"to append concurrently ({exc})"
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ConfigError(
                    "another gate process holds the execution-log lock; refusing "
                    f"to append concurrently ({exc})"
                ) from exc
        locked = True
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                # The descriptor is closed immediately below regardless; a
                # failed unlock must not mask the original outcome.
                pass
        os.close(fd)


def classify_log_state(log_path: Path, before_digest: str | None) -> str:
    """Return ``unchanged``, ``changed`` or ``unverifiable`` after a failure.

    Content digest, never file size: a same-length rewrite is still a change.
    ``unverifiable`` is returned when no baseline was captured or the log cannot
    be re-read, and is the only honest answer in those cases.
    """

    if before_digest is None:
        return "unverifiable"
    try:
        return (
            "unchanged"
            if digest_file(log_path) == before_digest
            else "changed"
        )
    except ConfigError:
        return "unverifiable"


def describe_log_state(state: str) -> str:
    """Human wording for a :func:`classify_log_state` result."""

    return {
        "unchanged": (
            "the log is byte-for-byte unchanged; nothing was written and the "
            "run remains open"
        ),
        "changed": (
            "the log CHANGED and may now end mid-record; every later append "
            "will refuse until a human inspects it"
        ),
        "unverifiable": (
            "the log's current state could not be established; it may be "
            "damaged and requires manual review"
        ),
    }[state]


def append_record(log_path: Path, record: dict) -> None:
    """Append one record and read it back. Any doubt raises; nothing warns."""

    payload = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")

    # ONE lock acquisition spans the lifecycle check, the append and the
    # read-back. Checking the lifecycle BEFORE taking the lock left a window in
    # which two gate processes could both pass the check and both append, which
    # can leave two open runs that only fail on a LATER read. The lock is
    # non-reentrant, so it is taken exactly once here and never nested.
    #
    # ``_load_orphan`` also calls ``log_is_intact`` outside any lock. That read
    # is advisory only: it locates a candidate for the operator to confirm. The
    # authoritative lifecycle decision is the one made below, under this lock.
    with log_write_lock(log_path):
        # An open run means a previous ``STARTED`` was never closed. Only a
        # terminal record may close it -- and it may do so only when there IS a
        # run to close, so the current run can never be closed by a later run's
        # terminal record. Any other status would either leave the trail
        # ambiguous or strand the log.
        open_run = log_is_intact(log_path)
        status = record.get("status")
        if status in RUN_TERMINAL_STATUSES:
            if open_run is None:
                raise ConfigError(
                    f"refusing to append a terminal record ({status!r}) while no "
                    "run is open: it would be an unmatched completion and would "
                    "misstate the audit trail"
                )
        elif open_run is not None:
            raise ConfigError(
                f"execution log line {open_run} opened a run (STARTED) that no "
                f"later record closed, and a {status!r} record cannot close it; "
                "that run's test outcome is unknown. No reconciliation is "
                "performed automatically. Refusing to append until it is "
                "resolved by hand"
            )
        try:
            fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                written = os.write(fd, payload)
                # Force the bytes to the device before reporting success, so a
                # later read-back cannot pass on data that is only in cache.
                try:
                    os.fsync(fd)
                except OSError:
                    # fsync is unsupported on some filesystems and handles. The
                    # read-back below still verifies what is visible; this is
                    # not a silent failure because the limitation is recorded.
                    pass
            finally:
                os.close(fd)
        except OSError as exc:
            raise ConfigError(f"execution record could not be written: {exc}") from exc
        if written != len(payload):
            raise ConfigError(
                f"short write to execution log ({written}/{len(payload)} bytes)"
            )

        try:
            lines = [
                ln for ln in log_path.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            if not lines:
                raise ConfigError(
                    "execution log is empty after a write that reported success"
                )
            if json.loads(lines[-1]) != record:
                raise ConfigError(
                    "execution record did not read back as written; another writer "
                    "may have interleaved. This run is refused, not recorded as clean."
                )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigError(
                f"execution record could not be verified: {exc}"
            ) from exc


def build_record(status: str, head: str, digest: str, audit_digest: str,
                 gate_digest: str, targets: list[str], deselects: list[str],
                 reason: str | None, absolute: list[str],
                 target_digests: dict[str, str] | None = None,
                 recovery: dict | None = None) -> dict:
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "head_sha": head,
        "allowlist_sha256": digest,
        "audit_sha256": audit_digest,
        "gate_sha256": gate_digest,
        "targets": targets,
        "targets_absolute": absolute,
        "target_sha256": dict(target_digests or {}),
        "deselects": deselects,
        "reason": reason,
    }
    if recovery is not None:
        # Recovery payload is additive and explicit. It never overwrites any
        # field above, so a historical record's shape is never altered.
        record.update(recovery)
    return record


def git_head(repo_root: Path) -> str:
    """Return HEAD, or raise. Called only AFTER validation completes."""

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigError(f"git HEAD could not be determined: {exc}") from exc
    head = (proc.stdout or "").strip()
    if proc.returncode != 0 or len(head) != 40:
        raise ConfigError(
            f"git HEAD could not be determined (exit {proc.returncode}); "
            "refusing to run without a verifiable repository identity"
        )
    return head


def _gate_digest_or_marker() -> str:
    """Best-effort gate digest for the no-Context fallback record.

    This path exists precisely because context creation failed, so the digest
    may be unobtainable. The marker is explicit rather than blank: a reader can
    tell "unknown" apart from "digest of an empty file".
    """

    try:
        return gate_source_digest()
    except ConfigError:
        return "<unavailable: gate source could not be digested>"


def _log_without_context(raw_targets: list[str], deselects: list[str],
                        reason: str, repo_root_arg: str) -> None:
    """Fallback refusal record for the case where no Context could be built.

    ``repo_root_arg`` is the value this invocation was actually given. It is
    passed in rather than re-derived from ``sys.argv`` so that a programmatic
    ``main(argv)`` call records its refusal in the repository it was pointed at,
    and never silently in a different one.

    Deliberately constrained: it writes only inside <repo_root>/tools and
    reports plainly when no validated configuration was available.
    """

    try:
        repo_root = Path(repo_root_arg).expanduser().resolve()
    except (OSError, ValueError, TypeError):
        print(
            "REFUSED: (durable logging unavailable: the repository root given "
            "for this invocation could not be resolved)",
            file=sys.stderr,
        )
        return
    log_path = repo_root / "tools" / "execution_log.jsonl"
    if not log_path.parent.is_dir():
        print("REFUSED: (durable logging unavailable: no tools/ directory)",
              file=sys.stderr)
        return
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REFUSED_NO_CONTEXT",
        "head_sha": "<not-resolved: validation had not completed>",
        "allowlist_sha256": "",
        "audit_sha256": "",
        "gate_sha256": _gate_digest_or_marker(),
        "repository_root": str(repo_root),
        "targets": raw_targets,
        "targets_absolute": [],
        "deselects": deselects,
        "reason": reason,
    }
    try:
        append_record(log_path, record)
    except ConfigError as exc:
        print(
            f"REFUSED: ({reason}) and the refusal could not be recorded ({exc})",
            file=sys.stderr,
        )


def _load_orphan(log_path: Path) -> tuple[int, dict]:
    """Re-read and validate the log, returning the single open ``STARTED``.

    Raises :class:`ConfigError` unless the log is structurally valid, contains
    exactly one open run, and that run is still open. This is the same
    validator every append uses, so reconciliation inherits its protections
    rather than re-implementing them.
    """

    open_line = log_is_intact(log_path)
    if open_line is None:
        raise ConfigError(
            "no orphaned STARTED record was found: the log has no open run, so "
            "there is nothing to reconcile. A repeated reconciliation lands here."
        )
    try:
        raw = log_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"execution log could not be re-read: {exc}") from exc
    # Physical line numbering, identical to ``log_is_intact``: enumerate over
    # ``splitlines()`` and skip blanks WITHOUT renumbering. Building a filtered
    # list here would disagree with the index ``log_is_intact`` returned and
    # could point the digest check at a different record.
    lines = raw.splitlines()
    if open_line > len(lines):
        raise ConfigError(
            f"orphan line {open_line} is beyond the end of the log "
            f"({len(lines)} physical lines)"
        )
    orphan_raw = lines[open_line - 1]
    if not orphan_raw.strip():
        raise ConfigError(
            f"orphan line {open_line} is blank; refusing to reconcile it"
        )
    try:
        orphan = json.loads(orphan_raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"orphan record at line {open_line} could not be parsed: {exc}"
        ) from exc
    if not isinstance(orphan, dict) or orphan.get("status") != "STARTED":
        raise ConfigError(
            f"line {open_line} is not a STARTED record; refusing to reconcile it"
        )
    return open_line, orphan


def reconcile_orphan(repo_root_arg: str, orphan_line: int | None,
                     failed_gate_sha256: str | None, dry_run: bool) -> int:
    """Close one orphaned ``STARTED`` with a truthful ``AUDIT_INCOMPLETE``.

    This asserts NOTHING about whether tests passed. The gate never recorded the
    old run's result, so the record states only that the audit is incomplete and
    which record is being reconciled. It cannot emit ``FINISHED`` or
    ``LAUNCH_FAILED``, and it never returns a test process result.
    """

    if orphan_line is None:
        return fail(
            "--reconcile-orphan requires --orphan-line (the 1-based log line "
            "holding the STARTED record to close)"
        )
    if failed_gate_sha256 is None:
        return fail(
            "--reconcile-orphan requires --failed-gate-sha256 (the full "
            "gate_sha256 stored in that STARTED record, used to prove which "
            "gate produced the orphan)"
        )
    try:
        _require_wellformed_digest(
            failed_gate_sha256, "gate_sha256 argument", orphan_line)
    except ConfigError:
        print(
            "ERROR: reconciliation refused; --failed-gate-sha256 must be a "
            "64-character lowercase hexadecimal SHA-256 digest, exactly as it "
            "appears in the orphan's gate_sha256 field. Nothing was appended.",
            file=sys.stderr,
        )
        return CONFIG_ERROR

    try:
        ctx = build_context(repo_root_arg)
    except ConfigError as exc:
        print(f"ERROR: reconciliation refused; configuration is not trustworthy "
              f"({exc})", file=sys.stderr)
        return CONFIG_ERROR

    try:
        open_line, orphan = _load_orphan(ctx.log_path)
    except ConfigError as exc:
        print(f"ERROR: reconciliation refused ({exc})", file=sys.stderr)
        return CONFIG_ERROR

    if open_line != orphan_line:
        print(
            f"ERROR: reconciliation refused; the open run is at line {open_line}, "
            f"not the requested line {orphan_line}", file=sys.stderr)
        return CONFIG_ERROR

    orphan_gate = orphan.get("gate_sha256")
    if not isinstance(orphan_gate, str) or len(orphan_gate) != 64:
        print(
            f"ERROR: reconciliation refused; the orphan at line {open_line} "
            "carries no usable gate_sha256 to bind against",
            file=sys.stderr,
        )
        return CONFIG_ERROR
    if orphan_gate != failed_gate_sha256:
        print(
            f"ERROR: reconciliation refused; --failed-gate-sha256 "
            f"{failed_gate_sha256} does not match the orphan's stored "
            f"gate_sha256 {orphan_gate}. The reconciliation would not describe "
            "the gate that produced this orphan.",
            file=sys.stderr,
        )
        return CONFIG_ERROR

    recovery = {
        "audit_completed": False,
        "test_process_result": "not_recorded_by_gate",
        "reconciles_orphan_line": open_line,
        "orphan_gate_sha256": orphan_gate,
        "reconciled_by_gate_sha256": ctx.gate_digest,
    }
    record = build_record(
        "AUDIT_INCOMPLETE", orphan.get("head_sha") or "<not-resolved>",
        ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest,
        orphan.get("targets") if isinstance(orphan.get("targets"), list) else [],
        orphan.get("deselects") if isinstance(orphan.get("deselects"), list) else [],
        "reconciliation: the previous run's audit was incomplete; this record "
        "asserts nothing about whether the tests passed",
        orphan.get("targets_absolute")
        if isinstance(orphan.get("targets_absolute"), list) else [],
        # Preserve the orphan's target digests only if it actually had a valid
        # mapping. Nothing is invented or reconstructed when they are absent.
        orphan.get("target_sha256")
        if isinstance(orphan.get("target_sha256"), dict) else None,
        recovery,
    )
    if "AUDIT_INCOMPLETE" in SUCCESS_STATUSES:
        raise RuntimeError("reconcile_orphan would emit a success status")
    if record["status"] not in RUN_TERMINAL_STATUSES:
        raise RuntimeError("reconcile_orphan would emit a non-terminal record")

    print("=== RECONCILIATION PLAN ===")
    print(f"  orphan line        : {open_line}")
    print(f"  orphan gate sha256 : {orphan_gate}")
    print(f"  reconciling gate   : {ctx.gate_digest}")
    print(f"  allowlist sha256   : {ctx.allowlist_digest}")
    print(f"  audit sha256       : {ctx.audit_digest}")
    print(f"  status             : {record['status']}")
    print(f"  audit_completed    : {record['audit_completed']}")
    print("  proposed record    :")
    print(json.dumps(record, sort_keys=True, indent=2))

    if dry_run:
        print("DRY RUN: reconciliation validated; the log was not modified.")
        return 0

    # Revalidate both configuration inputs immediately before writing, using the
    # same pattern normal execution uses. If either digest drifted since
    # build_context, refuse rather than cite a digest that no longer matches the
    # file on disk.
    try:
        for label, path, expected in (
            ("allowlist", ctx.allowlist_path, ctx.allowlist_digest),
            ("exclusion audit", ctx.audit_path, ctx.audit_digest),
        ):
            if digest_file(path) != expected:
                raise ConfigError(
                    f"{label} changed during reconciliation; refusing to record "
                    "a digest that no longer matches the file on disk"
                )
    except ConfigError as exc:
        print(
            f"ERROR: reconciliation refused ({exc}); nothing was appended",
            file=sys.stderr,
        )
        return CONFIG_ERROR

    # Capture the exact log CONTENT before the append, so a failure can be
    # reported honestly. Size alone would not distinguish an unchanged log from
    # a same-length rewrite, so the digest is what gets compared.
    try:
        before_digest = digest_file(ctx.log_path)
    except ConfigError:
        before_digest = None

    try:
        append_record(ctx.log_path, record)
    except ConfigError as exc:
        after_state = "unverifiable"
        if before_digest is not None:
            try:
                after_state = (
                    "unchanged"
                    if digest_file(ctx.log_path) == before_digest
                    else "changed"
                )
            except ConfigError:
                after_state = "unverifiable"
        detail = {
            "unchanged": (
                "the log is byte-for-byte unchanged and the orphan is still open"
            ),
            "changed": (
                "the log CHANGED and may now end mid-record; every later append "
                "will refuse until a human inspects it"
            ),
            "unverifiable": (
                "the log's current state could not be established; it may be "
                "damaged and requires manual review"
            ),
        }[after_state]
        print(
            f"ERROR: the AUDIT_INCOMPLETE record could not be persisted ({exc}). "
            f"No complete record was written and none was invented: {detail}. "
            "Nothing was truncated, rolled back or retried.",
            file=sys.stderr,
        )
        return CONFIG_ERROR
    print(
        f"RECONCILED: appended one AUDIT_INCOMPLETE record closing the run at "
        f"line {open_line}. No test process was created and no test result is "
        f"asserted. Exit {RECONCILED} is not a pytest code."
    )
    return RECONCILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed gate for research-engine test execution."
    )
    parser.add_argument("--targets", nargs="+", default=[],
                        help="explicit relative .py targets under the test root")
    parser.add_argument("--deselect", nargs="*", default=[],
                        help="explicit 'relative/path.py::<node>' deselections")
    parser.add_argument("--repo-root", default=None,
                        help="repository root; every other path derives from it")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and print the plan without executing")
    parser.add_argument("--reconcile-orphan", action="store_true",
                        help="close one orphaned STARTED with AUDIT_INCOMPLETE; "
                             "never runs tests and asserts no test result")
    parser.add_argument("--orphan-line", type=int, default=None,
                        help="1-based log line holding the STARTED to reconcile")
    parser.add_argument("--failed-gate-sha256", default=None,
                        help="full gate_sha256 stored in that STARTED record")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TEST_TIMEOUT_SECONDS,
                        help="wall-clock limit for the pytest process; the process "
                             "is killed and TIMEOUT is recorded if it is exceeded. "
                             "Must be positive; 0 disables the limit and is recorded "
                             "as such")
    args = parser.parse_args(argv)
    if args.timeout_seconds < 0:
        print("ERROR: --timeout-seconds must be >= 0", file=sys.stderr)
        return CONFIG_ERROR
    if args.reconcile_orphan:
        if args.targets:
            print(
                "ERROR: --reconcile-orphan cannot be combined with --targets; "
                "reconciliation runs no tests", file=sys.stderr)
            return CONFIG_ERROR
        if args.deselect:
            print(
                "ERROR: --reconcile-orphan cannot be combined with --deselect; "
                "reconciliation runs no tests", file=sys.stderr)
            return CONFIG_ERROR
        return reconcile_orphan(
            args.repo_root or str(Path(__file__).resolve().parents[1]),
            args.orphan_line, args.failed_gate_sha256, args.dry_run,
        )
    repo_root_arg = args.repo_root or str(Path(__file__).resolve().parents[1])

    ctx: Context | None = None
    raw_targets = [t for t in args.targets if t.strip()]
    raw_deselects = list(args.deselect)
    rel_files: list[str] = []
    absolute: list[str] = []
    target_digests: dict[str, str] = {}
    head = ""

    # ---- (a) VALIDATION: filesystem and text only, NO subprocess ----------
    try:
        ctx = build_context(repo_root_arg)

        if not raw_targets:
            raise Refusal(
                "no targets supplied. An empty target list is not permission "
                "to discover tests."
            )

        seen: set[str] = set()
        for raw in raw_targets:
            rel = validate_target(ctx, raw)
            if rel in seen:
                continue
            seen.add(rel)
            rel_files.append(rel)
            resolved = resolve_existing_file(ctx, rel, "target")
            absolute.append(str(resolved))
            # Digested as part of validation: this fixes the content that was
            # checked, so the same bytes can be proven at launch time (M-3).
            target_digests[rel] = digest_file(resolved)

        for raw in raw_deselects:
            validate_deselect(ctx, raw)

    except Refusal as exc:
        if ctx is not None:
            try:
                append_record(ctx.log_path, build_record(
                    "REFUSED", "<not-resolved>", ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest,
                    raw_targets, raw_deselects, str(exc), []))
            except ConfigError as log_exc:
                print(f"REFUSED: ({exc}) and the refusal could not be recorded "
                      f"({log_exc})", file=sys.stderr)
        else:
            _log_without_context(raw_targets, raw_deselects, str(exc), repo_root_arg)
        return fail(str(exc))

    except ConfigError as exc:
        if ctx is not None:
            try:
                append_record(ctx.log_path, build_record(
                    "REFUSED_CONFIG", "<not-resolved>", ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest,
                    raw_targets, raw_deselects, f"CONFIG: {exc}", []))
            except ConfigError as log_exc:
                print(f"ERROR: ({exc}) and the record could not be written "
                      f"({log_exc})", file=sys.stderr)
        else:
            _log_without_context(raw_targets, raw_deselects, f"CONFIG: {exc}",
                                 repo_root_arg)
        print(f"ERROR: {exc}", file=sys.stderr)
        return CONFIG_ERROR
    # ---- end (a) validation ------------------------------------------------

    if ctx is None:  # defensive: unreachable, never an assert
        return fail("internal: validation produced no context", CONFIG_ERROR)

    # ---- (b) Git metadata subprocess: AFTER validation, BEFORE pre-run log --
    try:
        head = git_head(ctx.repo_root)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return CONFIG_ERROR

    argv_plan = [
        sys.executable, "-m", "pytest",
        *absolute,
        *sum((["--deselect", d] for d in raw_deselects), []),
        "-v",
    ]

    print("=== RESOLVED TEST EXECUTION PLAN ===")
    print(f"  repository root : {ctx.repo_root}")
    print(f"  test root       : {ctx.test_root}")
    print(f"  git HEAD        : {head}")
    print(f"  allowlist       : {ctx.allowlist_path}")
    print(f"  allowlist sha256: {ctx.allowlist_digest}")
    print(f"  audit sha256    : {ctx.audit_digest}")
    print(f"  gate sha256    : {ctx.gate_digest}")
    print(f"  exclusion audit : {ctx.audit_path} "
          f"({ctx.audit_record_count} records)")
    print(f"  execution log   : {ctx.log_path}")
    print("  target files (printed form == executed form):")
    for rel, abs_path in zip(rel_files, absolute):
        print(f"        {rel}  ->  {abs_path}")
        print(f"            sha256: {target_digests.get(rel)}")
    print("  deselects       :")
    for d in raw_deselects or ["(none)"]:
        print(f"      {d}")
    print("  command         :")
    print("      " + " ".join(argv_plan))

    if not any(a.endswith(".py") for a in argv_plan[2:]):
        return fail("internal: resolved plan contains no explicit test file")

    if args.dry_run:
        print("DRY RUN: plan validated; nothing executed.")
        try:
            append_record(ctx.log_path, build_record(
                "DRY_RUN", head, ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest, rel_files,
                raw_deselects, None, absolute, target_digests))
        except ConfigError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return CONFIG_ERROR
        return 0

    # ---- (c) pre-run record, with a re-check of BOTH configuration inputs ----
    #
    # Capture the exact log CONTENT now, so any later append failure can report
    # a verified state rather than a guess. Size alone would not distinguish an
    # unchanged log from a same-length rewrite.
    try:
        before_digest = digest_file(ctx.log_path)
    except ConfigError:
        before_digest = None
    #
    # The allowlist and the exclusion audit are the two files that decide what may
    # run. The audit is the component that protects reserved tests, so neither may
    # change between validation and launch: both digests are re-read here, as late
    # as possible, and any drift refuses the run before pytest exists.
    #
    # The resolved targets are re-read for the same reason. Validation proved what
    # they contained; this proves they still contain it, so the bytes handed to
    # pytest are the bytes that were inspected.
    try:
        for label, path, expected in (
            ("allowlist", ctx.allowlist_path, ctx.allowlist_digest),
            ("exclusion audit", ctx.audit_path, ctx.audit_digest),
        ):
            if digest_file(path) != expected:
                raise ConfigError(
                    f"{label} changed during validation; refusing to record or "
                    "execute against a configuration that is no longer the one "
                    "that was validated"
                )
        for rel, abs_path in zip(rel_files, absolute):
            current = digest_file(Path(abs_path))
            if current != target_digests.get(rel):
                raise ConfigError(
                    f"target {rel!r} changed between validation and launch "
                    f"({target_digests.get(rel)} -> {current}); refusing to "
                    "execute content that was not the content validated"
                )
        # Revalidate the gate's own source and the repository identity. The
        # records written below must describe the code and the commit that are
        # actually executing, not the ones present when this process started.
        # NOTE: these checks narrow the window; they do not eliminate it. A
        # time-of-check/time-of-use race still exists between this block and
        # subprocess.run below, and no filesystem check can close it.
        if gate_source_digest() != ctx.gate_digest:
            raise ConfigError(
                "the gate source changed between validation and launch; refusing "
                "to execute under source that was not the source validated"
            )
        if git_head(ctx.repo_root) != head:
            raise ConfigError(
                "the repository HEAD changed between validation and launch; "
                "refusing to execute against a commit that was not the commit "
                "validated"
            )
        append_record(ctx.log_path, build_record(
            "STARTED", head, ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest, rel_files,
            raw_deselects, None, absolute, target_digests))
    except ConfigError as exc:
        state = classify_log_state(ctx.log_path, before_digest)
        print(f"ERROR: pre-run audit record could not be persisted ({exc}); "
              f"refusing to execute. Log state: {describe_log_state(state)}",
              file=sys.stderr)
        return CONFIG_ERROR

    # ---- (d) pytest --------------------------------------------------------
    timeout = args.timeout_seconds if args.timeout_seconds > 0 else None
    run_kwargs = {"cwd": ctx.test_root, "capture_output": True, "text": True}
    if timeout is not None:
        run_kwargs["timeout"] = timeout
    try:
        proc = subprocess.run(argv_plan, **run_kwargs)
    except (OSError, ValueError) as exc:
        # The test process never started. This is NOT a pytest result.
        print(f"ERROR: tests could not be launched ({exc}); no test process was "
              "created", file=sys.stderr)
        try:
            append_record(ctx.log_path, build_record(
                "LAUNCH_FAILED", head, ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest, rel_files,
                raw_deselects, f"launch failed: {exc}", absolute, target_digests))
        except ConfigError as log_exc:
            print(f"ERROR: tests could not be launched ({exc}) AND the failure "
                  f"could not be recorded ({log_exc}). No successful record "
                  "exists and none has been invented.", file=sys.stderr)
        return CONFIG_ERROR
    except subprocess.TimeoutExpired as exc:
        # The process WAS created and has been killed; its outcome is unknown.
        # This is deliberately NOT LAUNCH_FAILED (which asserts no process was
        # created) and NOT FINISHED (which would invent a pytest result).
        print(f"ERROR: the pytest process exceeded the {timeout}s limit and was "
              f"killed; its outcome is UNKNOWN and no pytest exit code is "
              f"claimed ({exc})", file=sys.stderr)
        try:
            append_record(ctx.log_path, build_record(
                "TIMEOUT", head, ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest, rel_files,
                raw_deselects, f"process killed after {timeout}s; outcome unknown; no pytest exit code",
                absolute, target_digests))
        except ConfigError as log_exc:
            print(f"ERROR: the timeout could not be recorded ({log_exc}); the log "
                  "is incomplete and requires manual review.", file=sys.stderr)
        return TIMED_OUT
    except (KeyboardInterrupt, SystemExit):
        # The process may or may not have been created and may still be running.
        # Record the truth we can support - outcome unknown - then re-raise so
        # the interpreter's own interrupt semantics are preserved.
        print("ERROR: interrupted while the pytest process was in flight; its "
              "outcome is UNKNOWN. Recording INTERRUPTED and re-raising.", file=sys.stderr)
        try:
            append_record(ctx.log_path, build_record(
                "INTERRUPTED", head, ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest, rel_files,
                raw_deselects, "gate interrupted while pytest was in flight; "
                "outcome unknown; no pytest exit code",
                absolute, target_digests))
        except ConfigError as log_exc:
            print(f"ERROR: the interruption could not be recorded ({log_exc}); the "
                  "log is incomplete and requires manual review.", file=sys.stderr)
        raise

    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    pytest_code = proc.returncode

    try:
        append_record(ctx.log_path, build_record(
            "FINISHED", head, ctx.allowlist_digest, ctx.audit_digest, ctx.gate_digest, rel_files,
            raw_deselects, f"pytest exit {pytest_code}", absolute, target_digests))
    except ConfigError as exc:
        state = classify_log_state(ctx.log_path, before_digest)
        print(f"PYTEST_EXIT_CODE={pytest_code}")
        print(
            "EXECUTION_OCCURRED_FINAL_LOG_FAILED: pytest DID run and returned "
            f"{pytest_code}. That is pytest's real exit code, reported "
            "separately and not this process's. The completion record could "
            f"not be persisted ({exc}), so the log is incomplete. Log state: "
            f"{describe_log_state(state)}. This exit status ({FINAL_LOG_FAILED}) "
            "reports the logging failure only and must not be read as a pytest "
            "result.",
            file=sys.stderr,
        )
        return FINAL_LOG_FAILED

    return pytest_code


if __name__ == "__main__":
    raise SystemExit(main())