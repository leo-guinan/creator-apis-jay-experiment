import argparse
import hashlib
import json
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
from threading import Thread

from build_synthetic_receipt import build_fixture
from creator_apis.api import ReportingAPI, create_handler
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


def _request(connection: HTTPConnection, method: str, path: str, *, body: dict | None = None, cookie: str | None = None):
    encoded = None if body is None else json.dumps(body).encode("utf-8")
    headers = {}
    if encoded is not None:
        headers = {"Content-Type": "application/json", "Content-Length": str(len(encoded))}
    if cookie:
        headers["Cookie"] = cookie
    connection.request(method, path, body=encoded, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    return response.status, dict(response.headers), json.loads(raw) if raw else {}


def _start(store: SQLiteLedgerStore):
    server = HTTPServer(("127.0.0.1", 0), create_handler(ReportingAPI(store=store)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_recovery(output_dir: str | Path) -> dict:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "restart-recovery.sqlite"
    if database.exists():
        database.unlink()
    store = _fresh_store(database)
    server, thread = _start(store)
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        click_status, click_headers, _ = _request(connection, "GET", "/r/route:jay-youtube-001")
        cookie = click_headers["Set-Cookie"].split(";", 1)[0]
        conversion_status, _, _ = _request(
            connection, "POST", "/v1/conversions",
            body={"conversion_id": "conversion:restart", "amount_cents": 100_000},
            cookie=cookie,
        )
        report_status, _, before_payload = _request(connection, "GET", "/v1/reports")
        connection.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
    before_hash = _sha256(database)

    restarted_store = SQLiteLedgerStore(database)
    restarted_server, restarted_thread = _start(restarted_store)
    try:
        connection = HTTPConnection("127.0.0.1", restarted_server.server_port)
        health_status, _, health = _request(connection, "GET", "/healthz")
        after_status, _, after_payload = _request(connection, "GET", "/v1/reports")
        connection.close()
    finally:
        restarted_server.shutdown()
        restarted_thread.join(timeout=2)
        restarted_server.server_close()
    after_hash = _sha256(database)
    receipt = {
        "receipt_version": "v1",
        "status": "verified" if (
            click_status == 302 and conversion_status == 201 and report_status == 200
            and health_status == 200 and after_status == 200
            and before_payload == after_payload and before_hash == after_hash
            and health.get("status") == "ok"
        ) else "failed",
        "before_restart": {"report": before_payload["report"], "report_status": report_status},
        "after_restart": {"report": after_payload["report"], "report_status": after_status, "health": health},
        "report_unchanged": before_payload == after_payload,
        "database_unchanged_after_restart": before_hash == after_hash,
        "database_sha256_before_restart": before_hash,
        "database_sha256_after_restart": after_hash,
    }
    (directory / "restart-recovery.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"restart-recovery: {receipt['status']}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local SQLite recovery across an HTTP server restart.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run_recovery(args.output_dir)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
