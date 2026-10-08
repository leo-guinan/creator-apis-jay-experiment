"""Exercise deliberate ledger corruption through every local verification boundary."""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from http.server import HTTPServer
from pathlib import Path
from threading import Thread

from creator_apis.api import ReportingAPI, create_handler
from creator_apis.sqlite_store import SQLiteLedgerStore
from build_synthetic_receipt import build_fixture
from verify_local_http import verify_http


def run_check(output: str | Path) -> dict:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="creator-apis-corruption-") as work:
        root = Path(work)
        database = root / "tampered.sqlite"
        SQLiteLedgerStore.create(database, build_fixture()[0])
        with sqlite3.connect(database) as connection:
            row = connection.execute("SELECT event_id, payload FROM events LIMIT 1").fetchone()
            event_id, payload = row
            connection.execute(
                "UPDATE events SET payload = ? WHERE event_id = ?",
                (payload.replace("route_click", "tampered_event", 1), event_id),
            )
            connection.commit()

        store = SQLiteLedgerStore(database)
        local_integrity = store.verify_integrity()
        backup = root / "backup.sqlite"
        restored = root / "restored.sqlite"
        with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        with sqlite3.connect(backup) as source, sqlite3.connect(restored) as target:
            source.backup(target)
        restored_integrity = SQLiteLedgerStore(restored).verify_integrity()

        api = ReportingAPI(store=store)
        dashboard = Path(__file__).resolve().parents[1] / "app" / "index.html"
        server = HTTPServer(("127.0.0.1", 0), create_handler(api, dashboard_path=dashboard))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        http_receipt = root / "http.json"
        try:
            http = verify_http(base_url, database, http_receipt)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        receipt = {
            "receipt_version": "v1",
            "status": "verified" if (
                local_integrity["status"] == "failed"
                and restored_integrity["status"] == "failed"
                and http["status"] == "failed"
                and http["integrity_status"] == "failed"
            ) else "failed",
            "fixture_status": "synthetic",
            "tamper": "changed one persisted event payload",
            "local_integrity": local_integrity,
            "restored_integrity": restored_integrity,
            "http_verification": http,
        }
    destination.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"corruption-pipeline: {receipt['status']}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deliberate corruption is rejected by local boundaries.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run_check(args.output)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
