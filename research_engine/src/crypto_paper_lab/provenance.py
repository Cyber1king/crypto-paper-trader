"""Provenance: publisher checksum verification and reproducible manifests.

Phase 46. The repository acquired data by hand in Phase 33 and recorded real
provenance in sidecar files -- including publisher checksums verified *before*
parsing. That discipline existed only as a one-off script. This module makes it
reusable, because "we did it carefully once" is not a property a pipeline can
rely on.

Two things live here, and neither touches the network:

* :func:`verify_publisher_checksum` compares a local archive against a
  publisher-published digest. Used before parsing, so corrupt bytes never reach
  a merge.
* :func:`build_manifest` / :func:`verify_manifest` produce and check a
  reproducible manifest: every input file, its size, its digest, and where it
  came from.

Deliberate limitations:

* Nothing here downloads. A missing file is an error, never a trigger to fetch.
* A publisher that publishes no checksum is recorded as
  ``checksum_published: False`` rather than being treated as verified. Absence of
  a digest is not evidence of integrity.
* Nothing here approves a dataset for research. It records what a file is.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "ProvenanceError",
    "ChecksumResult",
    "ArchiveRecord",
    "DatasetManifest",
    "sha256_of_file",
    "verify_publisher_checksum",
    "build_manifest",
    "verify_manifest",
    "write_manifest",
    "MANIFEST_VERSION",
]

MANIFEST_VERSION = 1

#: Read size for digesting. Large enough to be efficient, small enough not to
#: exhaust memory on a multi-hundred-megabyte archive.
_CHUNK = 1024 * 1024


class ProvenanceError(RuntimeError):
    """Raised when provenance cannot be established.

    ``RuntimeError`` rather than ``ValueError`` so it is never swallowed by a
    broad data-validation handler: a provenance failure is a different class of
    problem from a malformed value.
    """


def sha256_of_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ChecksumResult:
    """Outcome of comparing a local file against a publisher digest."""

    path: str
    published_sha256: str
    local_sha256: str
    verified: bool

    @property
    def status(self) -> str:
        return "verified" if self.verified else "mismatch"

    def as_record(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "published_sha256": self.published_sha256,
            "local_sha256": self.local_sha256,
            "verified": self.verified,
            "status": self.status,
        }


def verify_publisher_checksum(
    path: str | Path,
    published_sha256: str,
    *,
    allow_mismatch: bool = False,
) -> ChecksumResult:
    """Compare a local archive against the publisher's own digest.

    Call this **before** parsing. A mismatch means the bytes are not what the
    publisher issued, and merging them would silently corrupt a dataset that
    later looked clean.

    ``allow_mismatch=True`` records the mismatch without raising, for the case
    where a file is being quarantined for inspection. It must never be used to
    let a mismatched archive into a merge.
    """

    target = Path(path)
    if not target.exists():
        raise ProvenanceError(
            f"cannot verify checksum: {target} does not exist. Nothing is "
            "downloaded automatically; supply the file and retry."
        )

    published = str(published_sha256 or "").strip().lower()
    if len(published) != 64 or any(c not in "0123456789abcdef" for c in published):
        raise ProvenanceError(
            f"published checksum for {target.name} is not a SHA-256 hex digest: "
            f"{published_sha256!r}. Refusing rather than assuming a format."
        )

    local = sha256_of_file(target)
    verified = local == published

    if not verified and not allow_mismatch:
        raise ProvenanceError(
            f"checksum mismatch for {target.name}: publisher published "
            f"{published}, local file is {local}. The archive is not what the "
            "publisher issued and must not be parsed. Quarantine it; do not "
            "merge it."
        )

    return ChecksumResult(
        path=str(target),
        published_sha256=published,
        local_sha256=local,
        verified=verified,
    )


@dataclass(frozen=True)
class ArchiveRecord:
    """One retrieved source file and everything needed to reproduce it."""

    filename: str
    source_url: str
    published_sha256: str | None
    local_sha256: str
    bytes: int
    retrieved_at: str
    checksum_verified: bool

    def as_record(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "source_url": self.source_url,
            "published_sha256": self.published_sha256,
            "local_sha256": self.local_sha256,
            "bytes": self.bytes,
            "retrieved_at": self.retrieved_at,
            "checksum_verified": self.checksum_verified,
        }

    @staticmethod
    def from_record(record: dict[str, Any]) -> "ArchiveRecord":
        missing = [
            field
            for field in (
                "filename", "source_url", "local_sha256", "bytes", "retrieved_at"
            )
            if field not in record
        ]
        if missing:
            raise ProvenanceError(
                "archive record is incomplete; missing: " + ", ".join(sorted(missing))
            )
        return ArchiveRecord(
            filename=str(record["filename"]),
            source_url=str(record["source_url"]),
            published_sha256=(
                str(record["published_sha256"])
                if record.get("published_sha256")
                else None
            ),
            local_sha256=str(record["local_sha256"]),
            bytes=int(record["bytes"]),
            retrieved_at=str(record["retrieved_at"]),
            checksum_verified=bool(record.get("checksum_verified", False)),
        )


@dataclass
class DatasetManifest:
    """A reproducible description of one dataset and every input that produced it.

    Contains no prices. It records *what the file is and where it came from*, so
    a later reader can reproduce the acquisition without trusting this
    repository's memory.
    """

    dataset_path: str
    dataset_sha256: str
    instrument_id: str
    venue: str
    timeframe: str
    source_provider: str
    built_at: str
    row_count: int | None = None
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    archives: list[ArchiveRecord] = field(default_factory=list)
    transformation: str | None = None
    notes: str | None = None

    def as_record(self) -> dict[str, Any]:
        return {
            "manifest_version": MANIFEST_VERSION,
            "dataset_path": self.dataset_path,
            "dataset_sha256": self.dataset_sha256,
            "instrument_id": self.instrument_id,
            "venue": self.venue,
            "timeframe": self.timeframe,
            "source_provider": self.source_provider,
            "built_at": self.built_at,
            "row_count": self.row_count,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "archives": [a.as_record() for a in self.archives],
            "transformation": self.transformation,
            "notes": self.notes,
        }

    @staticmethod
    def from_record(record: dict[str, Any]) -> "DatasetManifest":
        if not isinstance(record, dict):
            raise ProvenanceError("manifest must be a JSON object")
        version = record.get("manifest_version")
        if version != MANIFEST_VERSION:
            raise ProvenanceError(
                f"manifest_version {version!r} is not supported; this "
                f"implementation writes version {MANIFEST_VERSION}"
            )
        missing = [
            field
            for field in (
                "dataset_path", "dataset_sha256", "instrument_id", "venue",
                "timeframe", "source_provider", "built_at",
            )
            if not str(record.get(field, "")).strip()
        ]
        if missing:
            raise ProvenanceError(
                "manifest is missing required field(s): " + ", ".join(sorted(missing))
            )
        return DatasetManifest(
            dataset_path=str(record["dataset_path"]),
            dataset_sha256=str(record["dataset_sha256"]),
            instrument_id=str(record["instrument_id"]),
            venue=str(record["venue"]),
            timeframe=str(record["timeframe"]),
            source_provider=str(record["source_provider"]),
            built_at=str(record["built_at"]),
            row_count=(
                int(record["row_count"]) if record.get("row_count") is not None else None
            ),
            first_timestamp=(
                str(record["first_timestamp"])
                if record.get("first_timestamp")
                else None
            ),
            last_timestamp=(
                str(record["last_timestamp"]) if record.get("last_timestamp") else None
            ),
            archives=[
                ArchiveRecord.from_record(a) for a in record.get("archives", [])
            ],
            transformation=(
                str(record["transformation"]) if record.get("transformation") else None
            ),
            notes=str(record["notes"]) if record.get("notes") else None,
        )

    @property
    def all_inputs_checksummed(self) -> bool:
        """True when every input archive was verified against a publisher digest.

        A dataset whose inputs have no publisher checksum is *reproducible* but
        not *publisher-verified*. Conflating the two would overstate evidence.
        """

        return bool(self.archives) and all(a.checksum_verified for a in self.archives)

    @property
    def provenance_ceiling(self) -> str:
        """Highest grade this manifest's own evidence supports.

        ``A`` requires every input verified against a publisher digest. Below
        that the manifest is honest about being weaker.
        """

        return "A" if self.all_inputs_checksummed else "B"


def build_manifest(
    dataset_path: str | Path,
    *,
    instrument_id: str,
    venue: str,
    timeframe: str,
    source_provider: str,
    archives: Iterable[ArchiveRecord] = (),
    row_count: int | None = None,
    first_timestamp: datetime | None = None,
    last_timestamp: datetime | None = None,
    transformation: str | None = None,
    notes: str | None = None,
    built_at: datetime | None = None,
) -> DatasetManifest:
    """Describe ``dataset_path`` and the archives that produced it.

    Hashes the file on disk rather than trusting a caller-supplied digest, so the
    manifest cannot record a hash that does not match the bytes.
    """

    target = Path(dataset_path)
    if not target.exists():
        raise ProvenanceError(
            f"cannot build a manifest for {target}: the file does not exist"
        )

    for name, value in (
        ("instrument_id", instrument_id),
        ("venue", venue),
        ("timeframe", timeframe),
        ("source_provider", source_provider),
    ):
        if not str(value).strip():
            raise ProvenanceError(
                f"{name} is required for a manifest; refusing to record an "
                "unattributed dataset"
            )

    stamp = built_at or datetime.now(timezone.utc)

    return DatasetManifest(
        dataset_path=str(target),
        dataset_sha256=sha256_of_file(target),
        instrument_id=str(instrument_id),
        venue=str(venue),
        timeframe=str(timeframe),
        source_provider=str(source_provider),
        built_at=stamp.isoformat(timespec="seconds"),
        row_count=row_count,
        first_timestamp=first_timestamp.isoformat() if first_timestamp else None,
        last_timestamp=last_timestamp.isoformat() if last_timestamp else None,
        archives=list(archives),
        transformation=transformation,
        notes=notes,
    )


def verify_manifest(
    manifest: DatasetManifest | dict[str, Any],
    root: str | Path,
    *,
    check_archives: bool = True,
) -> list[str]:
    """Re-verify a manifest against files on disk.

    Returns a list of problems; empty means everything matched. Returns rather
    than raises so a caller can report *all* discrepancies at once instead of
    discovering them one run at a time.
    """

    if not isinstance(manifest, DatasetManifest):
        manifest = DatasetManifest.from_record(manifest)

    base = Path(root)
    problems: list[str] = []

    target = base / manifest.dataset_path
    if not target.exists():
        problems.append(f"dataset missing: {manifest.dataset_path}")
    else:
        actual = sha256_of_file(target)
        if actual != manifest.dataset_sha256:
            problems.append(
                f"dataset digest changed for {manifest.dataset_path}: manifest "
                f"records {manifest.dataset_sha256}, file is {actual}"
            )

    if check_archives:
        for archive in manifest.archives:
            candidate = base / archive.filename
            if not candidate.exists():
                problems.append(f"archive missing: {archive.filename}")
                continue
            actual = sha256_of_file(candidate)
            if actual != archive.local_sha256:
                problems.append(
                    f"archive digest changed for {archive.filename}: manifest "
                    f"records {archive.local_sha256}, file is {actual}"
                )
            if archive.published_sha256 and not archive.checksum_verified:
                problems.append(
                    f"archive {archive.filename} records a published checksum "
                    "but was never verified against it"
                )

    return problems


def write_manifest(manifest: DatasetManifest, path: str | Path) -> Path:
    """Write a manifest as JSON.

    ``sort_keys`` and a fixed indent keep the output byte-stable for identical
    inputs, which is what makes a manifest diffable across acquisitions.
    """

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest.as_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target