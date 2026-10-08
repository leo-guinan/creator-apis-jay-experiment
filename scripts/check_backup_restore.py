import argparse
import hashlib
import json
import sqlite3
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
from threading import Thread

from build_synthetic_receipt import build_fixture
from creator_apis.api import ReportingAPI, create_handler
from creator_apis.reporting import LedgerReport
from creator_apis.sqlite_store import SQLiteLedgerStore


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fresh_store(path: Path) -> SQLiteLedgerStore:
    ledger, _ = build_fixture()
    ledger.events.clear()
    ledger.conversions.clear()
    return SQLiteLedgerStore.create(path, ledger)


def _request(connection, method, path, body=None, cookie=None):
    encoded = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if encoded is None else {"Content-Type": "application/json", "Content-Length": str(len(encoded))}
    if cookie:
        headers["Cookie"] = cookie
    connection.request(method, path, body=encoded, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    return response.status, dict(response.headers), json.loads(raw) if raw else {}


def _start(store):
    server = HTTPServer(("127.0.0.1", 0), create_handler(ReportingAPI(store=store)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_check(output_dir: str | Path) -> dict:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    source_path = directory / "source.sqlite"
    backup_path = directory / "backup.sqlite"
    restored_path = directory / "restored.sqlite"
    for path in (source_path, backup_path, restored_path):
        if path.exists():
            path.unlink()
    store = _fresh_store(source_path)
    server, thread = _start(store)
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        click_status, click_headers, _ = _request(connection, "GET", "/r/route:jay-youtube-001")
        cookie = click_headers["Set-Cookie"].split(";", 1)[0]
        conversion_status, _, _ = _request(
            connection, "POST", "/v1/conversions",
            {"conversion_id": "conversion:backup", "amount_cents": 100_000}, cookie,
        )
        report_status, _, before_payload = _request(connection, "GET", "/v1/reports")
        connection.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as backup:
        source.backup(backup)
    with sqlite3.connect(backup_path) as backup, sqlite3.connect(restored_path) as restored:
        backup.backup(restored)
    source_ledger = SQLiteLedgerStore(source_path).load()
    restored_ledger = SQLiteLedgerStore(restored_path).load()
    restored_report = LedgerReport(restored_ledger).summary(royalty_rate=0.10)
    restored_payload = {"api_version": "v1", "report": restored_report}
    receipt = {
        "receipt_version": "v1",
        "status": "verified" if (
            click_status == 302 and conversion_status == 201 and report_status == 200
            and before_payload == restored_payload
            and source_ledger.export() == restored_ledger.export()
        ) else "failed",
        "before_report": before_payload["report"],
        "restored_report": restored_report,
        "report_unchanged": before_payload == restored_payload,
        "logical_state_unchanged": source_ledger.export() == restored_ledger.export(),
        "source_sha256": _sha256(source_path),
        "backup_sha256": _sha256(backup_path),
        "restored_sha256": _sha256(restored_path),
    }
    (directory / "backup-restore.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"backup-restore: {receipt['status']}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local SQLite backup and restore fidelity.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run_check(args.output_dir)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
