"""Independently verify a local JSONL event-batch receipt against SQLite."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from creator_apis.backup_provenance import report_digest
from creator_apis.sqlite_store import SQLiteLedgerStore


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_receipt(receipt_path: str | Path) -> dict:
    receipt_path = Path(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    input_path = Path(receipt["input_path"])
    database = Path(receipt["database"])
    if not input_path.exists():
        errors.append("input file is missing")
    if not database.exists():
        errors.append("database is missing")
    if not errors:
        actual_input_hash = _file_hash(input_path)
        if actual_input_hash != receipt["input_sha256"]:
            errors.append("input hash mismatch")
        expected_batch_id = f"batch:{input_path.stem}:{actual_input_hash[:16]}"
        if expected_batch_id != receipt["batch_id"]:
            errors.append("batch ID mismatch")
        store = SQLiteLedgerStore(database)
        actual_integrity = store.verify_integrity()
        actual_report = report_digest(store)
        if actual_integrity != receipt["integrity_after"]:
            errors.append("after-integrity mismatch")
        if actual_report != receipt["report_sha256_after"]:
            errors.append("after-report digest mismatch")
        source_keys = {
            (event.get("source_name"), event.get("source_event_id"))
            for event in store.load().events
            if event.get("source_name") and event.get("source_event_id")
        }
        accepted = [item for item in receipt["outcomes"] if item["outcome"] == "accepted"]
        if receipt["status"] == "applied":
            for item in accepted:
                if (item.get("source_name"), item.get("source_event_id")) not in source_keys:
                    errors.append(f"accepted source event missing: {item.get('source_event_id')}")
        status = receipt["status"]
        if status in {"rejected_atomic", "dry_run"}:
            if receipt["integrity_before"] != receipt["integrity_after"]:
                errors.append("non-applied batch changed integrity")
            if receipt["report_sha256_before"] != receipt["report_sha256_after"]:
                errors.append("non-applied batch changed report")
        if status == "applied" and receipt["counts"]["applied"] != receipt["counts"]["accepted"]:
            errors.append("applied count differs from accepted count")
        if status == "rejected_atomic" and receipt["counts"]["applied"] != 0:
            errors.append("rejected atomic batch reports applied rows")
    result = {
        "verification_version": "v1",
        "status": "verified" if not errors else "failed",
        "receipt": str(receipt_path),
        "errors": errors,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local event-batch receipt independently.")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = verify_receipt(args.receipt)
    print(f"batch-verification: {result['status']}")
    if result["errors"]:
        print("; ".join(result["errors"]))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
