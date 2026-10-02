"""Phase 10 step 3: write a provenance sidecar for every downloaded archive."""
import hashlib
import zipfile
from datetime import date
from pathlib import Path

RAW = Path("data/oos/raw")
OOS = Path("data/oos")
BASE_URL = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04",
          "2026-05", "2026-06", "2026-07", "2026-08"]
UNAVAILABLE = ["2026-09", "2026-10", "2026-11", "2026-12"]
RETRIEVED = "2026-10-01"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    for month in MONTHS:
        archive = RAW / f"BTCUSDT-1h-{month}.zip"
        checksum_file = Path(f"{archive}.CHECKSUM")
        if not archive.exists():
            print(f"MISSING {archive}")
            continue

        published = checksum_file.read_text(encoding="utf-8").split()[0].strip()
        local = sha256(archive)
        verified = published.lower() == local.lower()

        with zipfile.ZipFile(archive) as zf:
            member = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            rows = len(zf.read(member).decode("utf-8").strip().splitlines())
            first_stamp = zf.read(member).decode("utf-8").splitlines()[0].split(",")[0]
            last_line = zf.read(member).decode("utf-8").strip().splitlines()[-1]
            last_stamp = last_line.split(",")[0]

        normalised = OOS / f"binance_spot_BTCUSDT_1h_{month.replace('-', '')}.csv"
        normalised_sha = sha256(normalised) if normalised.exists() else "n/a"
        report = OOS / f"{normalised.name}.report.txt"
        report_exists = report.exists()

        sidecar = RAW / f"BTCUSDT-1h-{month}.provenance.txt"
        sidecar.write_text(
            "\n".join([
                "SOURCE PROVENANCE - Binance Vision public market data",
                "=" * 62,
                "",
                "Source              : Binance Vision (data.binance.vision)",
                "Official URL        : "
                f"{BASE_URL}/BTCUSDT-1h-{month}.zip",
                "Checksum URL        : "
                f"{BASE_URL}/BTCUSDT-1h-{month}.zip.CHECKSUM",
                f"Archive filename    : {archive.name}",
                f"Archive bytes       : {archive.stat().st_size}",
                f"Retrieval date      : {RETRIEVED}",
                f"Published SHA-256   : {published}",
                f"Local SHA-256       : {local}",
                f"Checksum verified   : {verified}",
                "",
                "Market              : BTC/USDT spot (not futures)",
                "Data type           : klines (candles)",
                "Interval            : 1h",
                f"Covered date range  : {month}-01 .. {month}-last day",
                f"Rows in archive     : {rows}",
                f"First open time     : {first_stamp} (epoch microseconds)",
                f"Last  open time     : {last_stamp} (epoch microseconds)",
                "",
                "PARSING / NORMALISATION NOTES",
                "-" * 62,
                "  * Epoch unit inferred per row as microseconds. Binance Vision",
                "    publishes SPOT timestamps in microseconds from 2025-01-01",
                "    onward and milliseconds before that.",
                "  * Source layout has no header row, so the names of the six",
                "    ignored trailing columns cannot be read from the file.",
                "    They are positional only: close time, quote asset volume,",
                "    number of trades, taker buy base asset volume, taker buy",
                "    quote asset volume, ignore.",
                "  * Normalisation is representation-only: epoch converted to",
                "    dd-mm-yyyy HH:MM and the file reduced to the six canonical",
                "    columns. No price, volume or timestamp value was altered.",
                "  * No gap was filled, no price interpolated, no candle",
                "    synthesised.",
                "",
                "DERIVED FILES",
                "-" * 62,
                f"  normalised csv    : {normalised.as_posix()}",
                f"  normalised sha256 : {normalised_sha}",
                f"  validation report : "
                f"{report.as_posix() if report_exists else 'n/a'}",
                "",
                "LICENCE",
                "-" * 62,
                "  Binance Vision data is provided under CC BY-NC-SA 4.0 together",
                "  with the Binance Vision Dataset Terms. Permitted uses include",
                "  academic research, non-monetised open educational projects and",
                "  algorithmic historical backtesting for personal non-production",
                "  research. Commercial use is excluded. Attribution to Binance",
                "  Vision is required on redistribution.",
                "",
                "This sidecar is a local record created by this project. It is not",
                "issued by Binance.",
                "",
            ]),
            encoding="utf-8",
        )
        print(f"wrote {sidecar.as_posix()}  (verified={verified}, rows={rows})")

    # note the unavailable months
    missing_note = RAW / "UNAVAILABLE_MONTHS.txt"
    missing_note.write_text(
        "\n".join([
            "Monthly archives that were probed and NOT available",
            "=" * 62,
            f"Probed on: {RETRIEVED}",
            f"Base URL: {BASE_URL}",
            "",
        ] + [
            f"  BTCUSDT-1h-{m}.zip  -> HTTP 404 Not Found"
            for m in UNAVAILABLE
        ] + [
            "",
            "Reason: Binance Vision publishes a monthly archive on the first",
            "Monday of the following month. On the retrieval date the first",
            "Monday of October 2026 (5 October) had not yet occurred, so the",
            "September 2026 monthly archive was not published. October 2026 was",
            "also still in progress and December 2026 is in the future.",
            "",
            "No data was substituted, estimated or synthesised for these months.",
            "",
        ]),
        encoding="utf-8",
    )
    print(f"wrote {missing_note.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
