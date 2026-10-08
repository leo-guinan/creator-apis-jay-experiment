import argparse
import hashlib
import json
from http.server import HTTPServer
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from build_synthetic_receipt import build_fixture
from creator_apis.api import ReportingAPI, create_handler
from creator_apis.reporting import LedgerReport
from creator_apis.sqlite_store import SQLiteLedgerStore

AMOUNT_CENTS = 100_000


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


def _request(connection: HTTPConnection, method: str, path: str, *, body: dict | None = None, cookie: str | None = None) -> tuple[int, dict, dict]:
    encoded = None if body is None else json.dumps(body).encode("utf-8")
    headers = {}
    if encoded is not None:
        headers.update({"Content-Type": "application/json", "Content-Length": str(len(encoded))})
    if cookie:
        headers["Cookie"] = cookie
    connection.request(method, path, body=encoded, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    payload = json.loads(raw) if raw else {}
    return response.status, dict(response.headers), payload


def _run(name: str, output_dir: Path) -> dict:
    database = output_dir / f"{name}.sqlite"
    if database.exists():
        database.unlink()
    store = _fresh_store(database)
    server = HTTPServer(("127.0.0.1", 0), create_handler(ReportingAPI(store=store)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    steps: list[dict] = []
    connection = HTTPConnection("127.0.0.1", server.server_port)
    try:
        cookie = None
        if name in ("direct", "ambiguous"):
            status, headers, _ = _request(connection, "GET", "/r/route:jay-youtube-001")
            set_cookie = headers.get("Set-Cookie")
            cookie = set_cookie.split(";", 1)[0] if set_cookie else None
            steps.append({"name": "youtube_route", "status": status, "location": headers.get("Location"), "set_cookie": bool(set_cookie)})
        if name == "ambiguous":
            status, headers, _ = _request(connection, "GET", "/r/route:jay-x-001", cookie=cookie)
            steps.append({"name": "x_route", "status": status, "location": headers.get("Location"), "set_cookie": bool(headers.get("Set-Cookie"))})
        conversion = {"conversion_id": f"conversion:http-{name}", "amount_cents": AMOUNT_CENTS}
        if name == "no-click":
            conversion["session_id"] = "session:http-no-click"
        status, _, _ = _request(connection, "POST", "/v1/conversions", body=conversion, cookie=cookie)
        steps.append({"name": "conversion", "status": status})
        status, _, response = _request(connection, "GET", "/v1/reports")
        steps.append({"name": "report", "status": status})
        remote_report = response["report"]
        status, _, remote_integrity = _request(connection, "GET", "/v1/integrity")
        steps.append({"name": "integrity", "status": status})
        before_hash = _sha256(database)
    finally:
        connection.close()
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
    expected = LedgerReport(SQLiteLedgerStore(database).load()).summary(royalty_rate=0.10)
    expected_integrity = SQLiteLedgerStore(database).verify_integrity()
    after_hash = _sha256(database)
    integrity_status = "verified" if remote_integrity == {"api_version": "v1", **expected_integrity} else "failed"
    report_status = "verified" if remote_report == expected else "failed"
    receipt = {
        "receipt_version": "v1",
        "scenario": name,
        "fixture_status": "synthetic",
        "status": "verified" if report_status == "verified" and integrity_status == "verified" and before_hash == after_hash else "failed",
        "steps": steps,
        "report_status": report_status,
        "integrity_status": integrity_status,
        "integrity": remote_integrity,
        "database_unchanged": before_hash == after_hash,
        "database_sha256_before": before_hash,
        "database_sha256_after": after_hash,
        "report": remote_report,
    }
    (output_dir / f"{name}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{name}: {receipt['status']} classification={remote_report['attributions'][0]['classification']}")
    return receipt


def run_replays(output_dir: str | Path) -> list[dict]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    return [_run(name, destination) for name in ("direct", "ambiguous", "no-click")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay synthetic scenarios through the localhost HTTP API.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "examples" / "http-scenario-receipts")
    args = parser.parse_args()
    receipts = run_replays(args.output_dir)
    return 0 if all(receipt["status"] == "verified" for receipt in receipts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
