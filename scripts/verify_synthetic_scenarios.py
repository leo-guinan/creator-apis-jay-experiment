import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from creator_apis.reporting import LedgerReport
from creator_apis.sqlite_store import SQLiteLedgerStore

SCENARIOS = ("direct", "ambiguous", "no-click")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_receipts(receipt_dir: str | Path) -> tuple[dict[str, Any], int]:
    directory = Path(receipt_dir)
    results: dict[str, Any] = {}
    failures = 0
    for name in SCENARIOS:
        receipt_path = directory / f"{name}.json"
        database_path = directory / f"{name}.sqlite"
        errors: list[str] = []
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            actual_report = LedgerReport(SQLiteLedgerStore(database_path).load()).summary(royalty_rate=0.10)
            if receipt.get("fixture_status") != "synthetic":
                errors.append("receipt fixture_status is not synthetic")
            if receipt.get("report") != actual_report:
                errors.append("receipt report differs from SQLite recomputation")
            database_sha256 = _sha256(database_path)
            receipt_sha256 = _sha256(receipt_path)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"readback error: {exc}")
            database_sha256 = None
            receipt_sha256 = None
        status = "verified" if not errors else "failed"
        if errors:
            failures += 1
        results[name] = {
            "status": status,
            "database_sha256": database_sha256,
            "receipt_sha256": receipt_sha256,
            "errors": errors,
        }
        print(f"{name}: {status}")
    verification = {
        "verification_version": "v1",
        "status": "verified" if failures == 0 else "failed",
        "scenarios_verified": len(SCENARIOS) - failures,
        "scenarios": results,
    }
    (directory / "verification.json").write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"verified={verification['scenarios_verified']}")
    return verification, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify local synthetic scenario receipts.")
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "examples" / "scenario-receipts",
    )
    args = parser.parse_args()
    _, failures = verify_receipts(args.receipt_dir)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
