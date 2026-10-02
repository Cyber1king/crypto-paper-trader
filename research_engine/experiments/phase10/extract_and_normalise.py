"""Phase 10 step 1: extract verified archives and normalise with Phase 9 tooling.

Uses the existing ``crypto_paper_lab.acquisition`` module. No competing
normalisation or validation logic is created here.

Refuses to parse any archive whose SHA-256 does not match the published
``.CHECKSUM``. Preserves the downloaded archives untouched.

Reproducibility
---------------
``data/oos/raw/extracted/`` is a derived, untracked working directory. Every
CSV in it is a byte-for-byte copy of the single CSV inside the corresponding
verified ``.zip``. :func:`ensure_extracted` therefore *reuses* an existing
file and only unpacks when one is missing, so the whole step can be re-run
from the ZIP archives alone on a fresh clone.

The extraction step never overwrites an existing file, and the two optional
positional arguments ``raw_dir`` and ``out_dir`` let a verification run be
redirected at a scratch tree so it cannot clobber the committed datasets::

    python experiments/phase10/extract_and_normalise.py [raw_dir] [out_dir]
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from crypto_paper_lab.acquisition import (  # noqa: E402
    AcquisitionError,
    normalize_source,
    sha256_of,
    write_report,
)

BASE_URL = (
    "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h"
)
RAW = Path("data/oos/raw")
WORK = RAW / "extracted"
OUT = Path("data/oos")
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04",
          "2026-05", "2026-06", "2026-07", "2026-08"]

#: expected hours per month in 2026 (not a leap year)
EXPECTED_HOURS = {
    "2026-01": 31 * 24, "2026-02": 28 * 24, "2026-03": 31 * 24,
    "2026-04": 30 * 24, "2026-05": 31 * 24, "2026-06": 30 * 24,
    "2026-07": 31 * 24, "2026-08": 31 * 24,
}


def sha256(path: Path) -> str:
    return sha256_of(path)


def verify(month: str, raw_dir: Path = RAW) -> tuple[bool, str, str]:
    """Return (verified, expected, actual) for one monthly archive."""

    archive = raw_dir / f"BTCUSDT-1h-{month}.zip"
    checksum_file = Path(f"{archive}.CHECKSUM")

    if not archive.exists() or not checksum_file.exists():
        return False, "", ""

    expected = checksum_file.read_text(encoding="utf-8").split()[0].strip().lower()
    actual = sha256(archive).lower()
    return expected == actual, expected, actual


def ensure_extracted(
    month: str,
    raw_dir: Path = RAW,
    work_dir: Path = WORK,
) -> tuple[Path | None, str]:
    """Return ``(csv_path, status)`` for one month.

    ``status`` is one of ``reused``, ``extracted`` or an error string.

    The single CSV inside the verified archive is the only thing needed.
    If an already-unpacked copy exists it is reused verbatim, so re-running
    never rewrites a file; otherwise it is unpacked from the ZIP.
    """

    archive = raw_dir / f"BTCUSDT-1h-{month}.zip"
    target = work_dir / f"BTCUSDT-1h-{month}.csv"

    if target.exists():
        return target, "reused"

    if not archive.exists():
        return None, f"archive missing: {archive.as_posix()}"

    try:
        with zipfile.ZipFile(archive) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if len(names) != 1:
                return None, f"expected 1 csv in archive, found {names}"
            work_dir.mkdir(parents=True, exist_ok=True)
            # "xb" would fail rather than clobber, but the exists() guard
            # above already guarantees the target is new.
            with zf.open(names[0]) as src, target.open("wb") as dst:
                dst.write(src.read())
    except (zipfile.BadZipFile, OSError) as exc:
        return None, f"extraction failed: {exc}"

    return target, "extracted"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    raw_dir = Path(argv[0]) if len(argv) > 0 else RAW
    out_dir = Path(argv[1]) if len(argv) > 1 else OUT
    work_dir = raw_dir / "extracted"

    print("=" * 96)
    print("PHASE 10 STEP 1 - EXTRACT AND NORMALISE (verified archives only)")
    print("=" * 96)
    print(f"source base url : {BASE_URL}")
    print(f"raw directory   : {raw_dir.as_posix()}")
    print(f"work directory  : {work_dir.as_posix()}  (derived, untracked)")
    print(f"output directory: {out_dir.as_posix()}")
    print()

    accepted = []
    rows = []

    for month in MONTHS:
        verified, expected, actual = verify(month, raw_dir)
        archive = raw_dir / f"BTCUSDT-1h-{month}.zip"
        print("-" * 96)
        print(f"{month}  archive={archive.name}  bytes={archive.stat().st_size}")
        print(f"  published sha256 : {expected}")
        print(f"  local    sha256 : {actual}")
        print(f"  VERIFIED        : {verified}")

        if not verified:
            print("  -> NOT PARSED: checksum verification failed")
            rows.append((month, False, 0, 0, None, None, "checksum failed"))
            continue

        csv_path, status = ensure_extracted(month, raw_dir, work_dir)
        if csv_path is None:
            print(f"  -> NOT PARSED: {status}")
            rows.append((month, True, 0, 0, None, None, "extraction failed"))
            continue

        target = out_dir / f"binance_spot_BTCUSDT_1h_{month.replace('-', '')}.csv"
        report = normalize_source(csv_path, target)
        report_path = out_dir / f"{target.name}.report.txt"
        write_report(report, report_path)

        print(f"  source csv      : {csv_path.as_posix()}  ({status})")
        print(f"  detected format : {report.source_format}")
        print(f"  rows seen       : {report.rows_seen}")
        print(f"  rows accepted   : {report.rows_accepted}")
        print(f"  first / last    : {report.first_timestamp} -> {report.last_timestamp}")
        print(f"  missing hours   : {len(report.missing_hours)}")
        print(f"  duplicates      : {len(report.duplicate_timestamps)}")
        print(f"  invalid rows    : {len(report.invalid_rows)}")
        print(f"  extra columns   : {report.extra_columns}")
        print(f"  errors          : {report.errors}")
        print(f"  output          : {target.as_posix()}  written={report.written}")
        print(f"  output sha256   : {report.output_sha256}")
        print(f"  report          : {report_path.as_posix()}")
        print(f"  ACCEPTED        : {report.accepted}")

        expected_hours = EXPECTED_HOURS[month]
        if report.rows_accepted != expected_hours:
            print(f"  NOTE: expected {expected_hours} hours for {month}, "
                  f"got {report.rows_accepted}")

        if report.accepted:
            accepted.append(month)
        rows.append((
            month, verified, report.rows_seen, report.rows_accepted,
            report.first_timestamp, report.last_timestamp,
            "accepted" if report.accepted else "rejected",
        ))

    print()
    print("=" * 96)
    print("PER-MONTH SUMMARY")
    print("=" * 96)
    print(f"  {'month':9s} {'verified':>9s} {'seen':>7s} {'accepted':>9s} "
          f"{'first':>17s} {'last':>17s}  status")
    for month, verified, seen, acc, first, last, status in rows:
        print(f"  {month:9s} {str(verified):>9s} {seen:>7d} {acc:>9d} "
              f"{str(first):>17s} {str(last):>17s}  {status}")

    print()
    print(f"months accepted: {len(accepted)} of {len(MONTHS)}")
    print(f"months         : {', '.join(accepted) if accepted else 'none'}")
    return 0 if len(accepted) == len(MONTHS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
