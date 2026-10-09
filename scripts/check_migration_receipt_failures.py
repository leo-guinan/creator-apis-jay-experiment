"""Exercise migration-receipt tamper and wrong-database rejection paths."""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

from creator_apis.evidence import EvidenceLedger
from creator_apis.sqlite_store import SQLiteLedgerStore
from verify_migration_receipt import verify


def ledger(suffix: str) -> EvidenceLedger:
    value = EvidenceLedger(fixture_status="synthetic", campaign_id=f"campaign:{suffix}", experiment_id="experiment:test")
    value.add_contributor(f"contributor:{suffix}", "Test")
    value.add_source(f"source:{suffix}", f"contributor:{suffix}")
    value.add_content_block(f"block:{suffix}", f"source:{suffix}")
    value.add_artifact(f"artifact:{suffix}", [f"block:{suffix}"])
    value.add_placement(f"placement:{suffix}", f"artifact:{suffix}", "x")
    value.add_route(f"route:{suffix}", f"placement:{suffix}", "https://example.test")
    return value


def run(output: str | Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="creator-apis-receipt-") as directory:
        root = Path(directory)
        clean = root / "clean.sqlite"
        wrong = root / "wrong.sqlite"
        SQLiteLedgerStore.create(clean, ledger("clean"))
        SQLiteLedgerStore.create(wrong, ledger("wrong"))
        with sqlite3.connect(clean) as connection:
            receipt = connection.execute("SELECT * FROM migration_receipts").fetchone()
            columns = [row[1] for row in connection.execute("PRAGMA table_info(migration_receipts)")]
        with sqlite3.connect(wrong) as connection:
            placeholders = ",".join("?" for _ in columns)
            connection.execute(f"UPDATE migration_receipts SET ({','.join(columns)}) = ({placeholders})", receipt)
        wrong_result = verify(wrong)
        with sqlite3.connect(clean) as connection:
            connection.execute("UPDATE migration_receipts SET report_sha256_after = 'tampered'")
        tampered_result = verify(clean)
    result = {"verification_version": "v1", "status": "verified" if wrong_result["status"] == "failed" and tampered_result["status"] == "failed" else "failed", "wrong_database": wrong_result, "tampered": tampered_result}
    destination = Path(output); destination.parent.mkdir(parents=True, exist_ok=True); destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"migration-receipt-negative-paths: {result['status']}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify migration receipt rejection paths.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run(args.output)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
