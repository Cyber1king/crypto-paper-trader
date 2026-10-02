"""Phase 8 harness self-test.

Proves the validation harness is functional code, not dead code, by feeding
it a SYNTHETIC post-2025 CSV built in a temporary directory.

IMPORTANT: the numbers produced here are generated from made-up prices. They
are a mechanical test of the harness (boundary handling, warm-up exclusion,
balance methodology). They are NOT a validation result and carry no research
meaning whatsoever. The real out-of-sample validation remains NOT PERFORMED
because the repository holds no unseen data.
"""
import csv
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE / "validation_harness.py"
START = datetime(2026, 1, 1, 0, 0)          # strictly after Phase 7


def synth_rows(n: int):
    """Deterministic synthetic hourly candles with up and down legs."""

    rows = []
    price = 95_000.0
    for i in range(n):
        rising = (i // 40) % 2 == 0
        if rising:
            rows.append((price, price + 250, price - 120, price + 250))
            price += 250
        else:
            rows.append((price, price + 120, price - 250, price - 250))
            price -= 250
    return rows


def write_csv(path: Path, n: int):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        for i, (o, h, l, c) in enumerate(synth_rows(n)):
            stamp = START + timedelta(hours=i)
            writer.writerow([
                stamp.strftime("%d-%m-%Y %H:%M"),
                f"{o:.2f}", f"{h:.2f}", f"{l:.2f}", f"{c:.2f}", "1234.5",
            ])


def main():
    print("=" * 100)
    print("PHASE 8 HARNESS SELF-TEST (SYNTHETIC DATA - NOT A VALIDATION RESULT)")
    print("=" * 100)
    print("This test only proves the harness code path works end to end.")
    print("The prices are invented. Nothing below is a research finding.")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "SYNTHETIC_VALIDATION.csv"
        write_csv(path, 480)     # 480 hourly candles from 2026-01-01
        print(f"\nsynthetic file: {path.name}  (480 candles from {START})")

        proc = subprocess.run(
            [sys.executable, str(HARNESS), str(path)],
            capture_output=True, text=True, cwd=str(HERE.parents[1]),
        )
        out = proc.stdout
        print(out)

        # mechanical assertions on the harness output
        checks = {
            "ran without rejection":
                "REJECTED" not in out,
            "reported a validation window":
                "validation window" in out,
            "excluded warm-up bars from trading":
                "warm-up (context)" in out,
            "documented balance methodology":
                "Balance methodology" in out,
            "documented end-of-window handling":
                "End-of-window" in out,
            "reported both configurations":
                "baseline" in out and "A2_min_dist_0.002" in out,
            "reported after-costs verdict":
                "after costs" in out,
            "zero exit code": proc.returncode == 0,
        }
        print("=" * 100)
        print("MECHANICAL CHECKS")
        print("=" * 100)
        for label, ok in checks.items():
            print(f"  {label:44s} {'PASS' if ok else 'FAIL'}")
        failed = [k for k, v in checks.items() if not v]
        print()
        if failed:
            print(f"SELF-TEST FAILED: {failed}")
            return 1
        print("HARNESS SELF-TEST PASSED - harness is ready for real unseen data.")
        print("Out-of-sample validation itself remains NOT PERFORMED.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
