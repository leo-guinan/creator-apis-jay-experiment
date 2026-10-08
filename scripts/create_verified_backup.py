"""Create a provenance receipt for a verified local SQLite backup."""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from creator_apis.backup_provenance import checkpoint, ledger_identity, report_digest, sha256_file
from creator_apis.sqlite_store import SQLiteLedgerStore


def create_backup(source: str | Path, backup: str | Path, receipt: str | Path) -> dict:
    source = Path(source)
    backup = Path(backup)
    receipt = Path(receipt)
    if not source.exists():
        raise FileNotFoundError(source)
    if backup.exists():
        raise FileExistsError(backup)
    source_store = SQLiteLedgerStore(source)
    source_integrity = source_store.verify_integrity()
    if source_integrity["status"] != "verified":
        raise ValueError("refusing backup: source integrity is not verified")
    checkpoint(source_store)
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection, sqlite3.connect(backup) as backup_connection:
        source_connection.backup(backup_connection)
    backup_store = SQLiteLedgerStore(backup)
    backup_integrity = backup_store.verify_integrity()
    if backup_integrity != source_integrity:
        raise ValueError("backup integrity differs from source")
    source_ledger = source_store.load()
    result = {
        "receipt_version": "v1",
        "status": "verified",
        "fixture_status": source_ledger.fixture_status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source),
        "backup_path": str(backup),
        "campaign_id": source_ledger.campaign_id,
        "experiment_id": source_ledger.experiment_id,
        "ledger_identity": ledger_identity(source_store),
        "report_sha256": report_digest(source_store),
        "source_integrity": source_integrity,
        "backup_integrity": backup_integrity,
        "source_sha256": sha256_file(source),
        "backup_sha256": sha256_file(backup),
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a verified local SQLite backup and provenance receipt.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = create_backup(args.source, args.backup, args.receipt)
    print(f"backup: {result['status']} root={result['backup_integrity']['root_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
