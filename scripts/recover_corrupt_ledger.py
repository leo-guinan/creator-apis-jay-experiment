"""Quarantine an invalid local ledger and restore a separately verified backup."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from creator_apis.backup_provenance import ledger_identity, report_digest, sha256_file
from creator_apis.sqlite_store import SQLiteLedgerStore


def _backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    with sqlite3.connect(source) as source_connection, sqlite3.connect(destination) as destination_connection:
        source_connection.backup(destination_connection)


def _move_sqlite_bundle(database: Path, quarantine: Path) -> list[str]:
    moved: list[str] = []
    for candidate in (database, Path(f"{database}-wal"), Path(f"{database}-shm")):
        if candidate.exists():
            target = quarantine / candidate.name
            shutil.move(str(candidate), str(target))
            moved.append(str(target))
    return moved


def recover_database(
    database: str | Path,
    verified_backup: str | Path,
    backup_receipt: str | Path,
    output_dir: str | Path,
    *,
    operator: str,
    reason: str,
) -> dict:
    database = Path(database)
    verified_backup = Path(verified_backup)
    backup_receipt = Path(backup_receipt)
    output_dir = Path(output_dir)
    if not database.exists():
        raise FileNotFoundError(database)
    if not verified_backup.exists():
        raise FileNotFoundError(verified_backup)
    if not backup_receipt.exists():
        raise FileNotFoundError(backup_receipt)
    receipt = json.loads(backup_receipt.read_text(encoding="utf-8"))
    active_store = SQLiteLedgerStore(database)
    before = active_store.verify_integrity()
    if before["status"] == "verified":
        raise ValueError("refusing recovery: active database is already verified")
    backup_integrity = SQLiteLedgerStore(verified_backup).verify_integrity()
    if backup_integrity["status"] != "verified":
        raise ValueError("refusing recovery: supplied backup is not verified")
    if Path(receipt.get("backup_path", "")).resolve() != verified_backup.resolve():
        raise ValueError("refusing recovery: backup receipt path mismatch")
    if receipt.get("backup_sha256") != sha256_file(verified_backup):
        raise ValueError("refusing recovery: backup file hash mismatch")
    if receipt.get("backup_integrity") != backup_integrity:
        raise ValueError("refusing recovery: backup receipt integrity mismatch")
    if receipt.get("ledger_identity") != ledger_identity(active_store):
        raise ValueError("refusing recovery: backup belongs to a different ledger identity")

    repair_id = f"repair:{uuid4()}"
    quarantine = output_dir / f"quarantine-{repair_id.split(':', 1)[1]}"
    quarantine.mkdir(parents=True, exist_ok=False)
    moved = _move_sqlite_bundle(database, quarantine)
    restored_tmp = output_dir / f".{database.name}.{repair_id.split(':', 1)[1]}.tmp"
    try:
        _backup(verified_backup, restored_tmp)
        os.replace(restored_tmp, database)
    except Exception:
        if restored_tmp.exists():
            restored_tmp.unlink()
        raise
    after = SQLiteLedgerStore(database).verify_integrity()
    receipt = {
        "receipt_version": "v1",
        "repair_id": repair_id,
        "status": "repaired" if after["status"] == "verified" else "failed",
        "fixture_status": SQLiteLedgerStore(database).load().fixture_status,
        "operator": operator,
        "reason": reason,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "active_database": str(database),
        "quarantined_files": moved,
        "quarantine_directory": str(quarantine),
        "source_backup": str(verified_backup),
        "backup_receipt": str(backup_receipt),
        "backup_provenance": {
            "ledger_identity": receipt["ledger_identity"],
            "report_sha256": receipt.get("report_sha256"),
            "backup_sha256": receipt["backup_sha256"],
        },
        "integrity_before": before,
        "backup_integrity": backup_integrity,
        "integrity_after": after,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / "repair-receipt.json"
    receipt["receipt_path"] = str(receipt_path)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine and restore an invalid local SQLite ledger.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--verified-backup", type=Path, required=True)
    parser.add_argument("--backup-receipt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    receipt = recover_database(
        args.database,
        args.verified_backup,
        args.backup_receipt,
        args.output_dir,
        operator=args.operator,
        reason=args.reason,
    )
    print(f"ledger-recovery: {receipt['status']} quarantine={receipt['quarantine_directory']}")
    return 0 if receipt["status"] == "repaired" else 1


if __name__ == "__main__":
    raise SystemExit(main())
