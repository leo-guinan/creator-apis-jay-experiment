"""Exercise legacy, current, and future SQLite schema states."""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

from creator_apis.backup_provenance import report_digest
from creator_apis.evidence import EvidenceLedger
from creator_apis.sqlite_store import SQLiteLedgerStore, SCHEMA_VERSION


def _ledger() -> EvidenceLedger:
    ledger = EvidenceLedger(fixture_status="synthetic", campaign_id="campaign:test", experiment_id="experiment:test")
    ledger.add_contributor("contributor:test", "Test")
    ledger.add_source("source:test", "contributor:test")
    ledger.add_content_block("block:test", "source:test")
    ledger.add_artifact("artifact:test", ["block:test"])
    ledger.add_placement("placement:test", "artifact:test", "x")
    ledger.add_route("route:test", "placement:test", "https://example.test")
    return ledger


def _make_legacy(path: Path) -> None:
    store = SQLiteLedgerStore.create(path, _ledger())
    store.set_source_status("source:test", "synthetic", operator="fixture", reason="legacy fixture", observed_at="2026-10-08T00:00:00Z")
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE source_decisions RENAME TO source_decisions_current")
        connection.execute("CREATE TABLE source_decisions (decision_id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL, previous_status TEXT NOT NULL, new_status TEXT NOT NULL, operator TEXT NOT NULL, reason TEXT NOT NULL, observed_at TEXT NOT NULL)")
        connection.execute("INSERT INTO source_decisions(decision_id, source_name, previous_status, new_status, operator, reason, observed_at) SELECT decision_id, source_name, previous_status, new_status, operator, reason, observed_at FROM source_decisions_current")
        connection.execute("DROP TABLE source_decisions_current")
        connection.execute("PRAGMA user_version = 0")


def run_check(output: str | Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="creator-apis-schema-") as directory:
        root = Path(directory)
        legacy = root / "legacy.sqlite"
        _make_legacy(legacy)
        upgraded = SQLiteLedgerStore(legacy)
        legacy_result = {"schema": upgraded.schema_status(), "integrity": upgraded.verify_integrity(), "decisions": upgraded.verify_source_decisions(), "report_sha256": report_digest(upgraded)}
        current = root / "current.sqlite"
        current_store = SQLiteLedgerStore.create(current, _ledger())
        current_before = (current_store.verify_integrity(), report_digest(current_store))
        current_after = SQLiteLedgerStore(current)
        current_result = {"schema": current_after.schema_status(), "integrity_same": current_after.verify_integrity() == current_before[0], "report_same": report_digest(current_after) == current_before[1]}
        future = root / "future.sqlite"
        SQLiteLedgerStore.create(future, _ledger())
        with sqlite3.connect(future) as connection:
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        try:
            SQLiteLedgerStore(future)
        except ValueError as exc:
            future_result = {"status": "blocked", "error": str(exc)}
        else:
            future_result = {"status": "accepted"}
    result = {"verification_version": "v1", "status": "verified" if legacy_result["schema"]["version"] == SCHEMA_VERSION and legacy_result["integrity"]["status"] == "verified" and legacy_result["decisions"]["status"] == "verified" and current_result["schema"]["status"] == "ready" and current_result["integrity_same"] and current_result["report_same"] and future_result["status"] == "blocked" else "failed", "legacy": legacy_result, "current": current_result, "future": future_result}
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"schema-matrix: {result['status']}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SQLite legacy/current/future schema behavior.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run_check(args.output)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
