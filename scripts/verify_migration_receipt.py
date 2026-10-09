"""Independently verify the durable SQLite migration receipt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from creator_apis.backup_provenance import ledger_identity, report_digest
from creator_apis.sqlite_store import SQLiteLedgerStore


def verify(database: str | Path) -> dict:
    store = SQLiteLedgerStore.__new__(SQLiteLedgerStore)
    store.path = Path(database)
    receipts = store.migration_receipts()
    errors = []
    if not receipts:
        errors.append("no migration receipt")
        receipt = None
    else:
        receipt = receipts[-1]
        integrity = store.verify_integrity()
        decisions = store.verify_source_decisions()
        if receipt["status"] != "applied":
            errors.append("receipt status is not applied")
        if receipt["ledger_identity"] != ledger_identity(store):
            errors.append("ledger identity mismatch")
        if receipt["event_root_after"] != integrity.get("root_hash"):
            errors.append("event root mismatch")
        if receipt["decision_root_after"] != decisions.get("root_hash"):
            errors.append("decision root mismatch")
        if receipt["report_sha256_after"] != report_digest(store):
            errors.append("report digest mismatch")
        if receipt["version_after"] != store.schema_status()["version"]:
            errors.append("schema version mismatch")
    result = {"verification_version": "v1", "status": "verified" if not errors else "failed", "database": str(database), "receipt": receipt, "errors": errors}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a SQLite migration receipt.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.database)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"migration-receipt: {result['status']}")
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
