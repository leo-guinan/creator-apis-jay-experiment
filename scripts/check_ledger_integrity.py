import argparse
import json
from pathlib import Path

from creator_apis.sqlite_store import SQLiteLedgerStore


def check_integrity(sqlite_path: str | Path, output: str | Path | None = None) -> dict:
    result = SQLiteLedgerStore(sqlite_path).verify_integrity()
    receipt = {"verification_version": "v1", **result}
    if output is not None:
        Path(output).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"status={receipt['status']} event_count={receipt['event_count']} root_hash={receipt['root_hash']}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the local SQLite event hash chain.")
    parser.add_argument("--sqlite", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return 0 if check_integrity(args.sqlite, args.output)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
