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


def _state_hash(path: Path) -> str:
    payload = json.dumps(SQLiteLedgerStore(path).load().export(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _fresh_store(path: Path) -> SQLiteLedgerStore:
    ledger, _ = build_fixture()
    ledger.events.clear()
    ledger.conversions.clear()
    return SQLiteLedgerStore.create(path, ledger)


def _request(connection: HTTPConnection, method: str, path: str, *, body=None, cookie=None, raw=False):
    encoded = body if raw else (None if body is None else json.dumps(body).encode("utf-8"))
    headers = {}
    if encoded is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(encoded))
    if cookie:
        headers["Cookie"] = cookie
    connection.request(method, path, body=encoded, headers=headers)
    response = connection.getresponse()
    response.read()
    return response.status


def run_checks(output_dir: str | Path) -> dict:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "negative-paths.sqlite"
    if database.exists():
        database.unlink()
    store = _fresh_store(database)
    server = HTTPServer(("127.0.0.1", 0), create_handler(ReportingAPI(store=store)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    try:
        connection.request("GET", "/r/route:jay-youtube-001")
        click = connection.getresponse()
        cookie = click.getheader("Set-Cookie").split(";", 1)[0]
        click.read()
        _request(connection, "POST", "/v1/conversions", body={"conversion_id": "conversion:negative-baseline", "amount_cents": 100_000}, cookie=cookie)
        baseline_hash = _state_hash(database)
        cases = [
            ("unknown_scenario", "GET", "/v1/reports?scenario=missing", None, None, 400, False),
            ("unknown_route_redirect", "GET", "/r/route:missing", None, None, 404, False),
            ("missing_session", "POST", "/v1/conversions", {"conversion_id": "conversion:missing-session", "amount_cents": 100}, None, 400, False),
            ("negative_amount", "POST", "/v1/conversions", {"conversion_id": "conversion:negative", "amount_cents": -1}, cookie, 400, False),
            ("unknown_conversion_field", "POST", "/v1/conversions", {"conversion_id": "conversion:field", "amount_cents": 100, "secret": "no"}, cookie, 400, False),
            ("malformed_json", "POST", "/v1/conversions", b"{not-json", cookie, 400, True),
            ("unknown_event_route", "POST", "/v1/events", {"event_id": "event:bad-route", "event_type": "route_click", "session_id": "session:bad", "route_id": "route:missing"}, None, 400, False),
            ("conversion_conflict", "POST", "/v1/conversions", {"conversion_id": "conversion:negative-baseline", "amount_cents": 999}, cookie, 400, False),
        ]
        results = []
        for name, method, path, body, case_cookie, expected, raw in cases:
            actual = _request(connection, method, path, body=body, cookie=case_cookie, raw=raw)
            results.append({"name": name, "expected": expected, "actual": actual, "status": "verified" if actual == expected else "failed"})
    finally:
        connection.close()
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
    after_hash = _state_hash(database)
    receipt = {
        "receipt_version": "v1",
        "status": "verified" if all(item["status"] == "verified" for item in results) and baseline_hash == after_hash else "failed",
        "checks": results,
        "database_unchanged": baseline_hash == after_hash,
        "database_sha256_before": baseline_hash,
        "database_sha256_after": after_hash,
    }
    (directory / "negative-paths.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"negative-paths: {receipt['status']} checks={len(results)}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local API negative paths and ledger preservation.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run_checks(args.output_dir)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
