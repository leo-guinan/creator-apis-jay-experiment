"""Exercise ready, degraded, and blocked local audit states."""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

from creator_apis.audit import audit_local_state
from creator_apis.api import ReportingAPI, create_handler
from creator_apis.sqlite_store import SQLiteLedgerStore
from build_synthetic_receipt import build_fixture
from create_verified_backup import create_backup
from import_event_batch import import_batch


def _fixture(root: Path) -> Path:
    database = root / "ledger.sqlite"
    SQLiteLedgerStore.create(database, build_fixture()[0])
    return database


def _http_status(database: Path, audit_paths: dict) -> int:
    api = ReportingAPI(store=SQLiteLedgerStore(database), audit_paths=audit_paths)
    server = HTTPServer(("127.0.0.1", 0), create_handler(api))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/v1/audit") as response:
                return response.status
        except HTTPError as exc:
            return exc.code
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def run_matrix(output: str | Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="creator-apis-audit-") as directory:
        root = Path(directory)
        ready_db = _fixture(root / "ready")
        ready_dir = root / "ready"
        ready_dir.mkdir(exist_ok=True)
        input_path = ready_dir / "import.jsonl"
        input_path.write_text(json.dumps({"source_name": "audit-fixture", "source_event_id": "evt-1", "event_type": "route_click", "route_id": "route:jay-youtube-001"}) + "\n", encoding="utf-8")
        import_receipt = ready_dir / "import-001.json"
        import_batch(ready_db, input_path, import_receipt, apply=True)
        backup_receipt = ready_dir / "backup-receipt.json"
        create_backup(ready_db, ready_dir / "backup.sqlite", backup_receipt)
        paths = {"backup_receipt": backup_receipt, "import_receipts": [import_receipt]}
        ready = audit_local_state(SQLiteLedgerStore(ready_db), **paths)
        ready_http = _http_status(ready_db, paths)

        degraded_db = _fixture(root / "degraded")
        degraded = audit_local_state(SQLiteLedgerStore(degraded_db))
        degraded_http = _http_status(degraded_db, {})

        blocked_db = _fixture(root / "blocked")
        with sqlite3.connect(blocked_db) as connection:
            event_id, payload = connection.execute("SELECT event_id, payload FROM events LIMIT 1").fetchone()
            connection.execute("UPDATE events SET payload = ? WHERE event_id = ?", (payload.replace("route_click", "tampered_event", 1), event_id))
            connection.commit()
        blocked = audit_local_state(SQLiteLedgerStore(blocked_db))
        blocked_http = _http_status(blocked_db, {})
    result = {
        "verification_version": "v1",
        "status": "verified" if (
            ready["status"] == "ready" and ready_http == 200
            and degraded["status"] == "degraded" and degraded_http == 200
            and blocked["status"] == "blocked" and blocked_http == 503
        ) else "failed",
        "states": {
            "ready": {"audit": ready, "http_status": ready_http},
            "degraded": {"audit": degraded, "http_status": degraded_http},
            "blocked": {"audit": blocked, "http_status": blocked_http},
        },
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"audit-matrix: {result['status']}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local audit ready/degraded/blocked states.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run_matrix(args.output)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
