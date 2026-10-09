import argparse
import json
from pathlib import Path

from creator_apis.audit import audit_local_state
from creator_apis.sqlite_store import SQLiteLedgerStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local Creator APIs state and receipts.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--backup-receipt", type=Path)
    parser.add_argument("--import-receipt", type=Path, action="append", default=[])
    parser.add_argument("--recovery-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_local_state(
        SQLiteLedgerStore(args.database),
        backup_receipt=args.backup_receipt,
        import_receipts=args.import_receipt,
        recovery_receipt=args.recovery_receipt,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"local-audit: {result['status']}")
    return 0 if result["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
