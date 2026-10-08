import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from creator_apis.reporting import LedgerReport
from creator_apis.sqlite_store import SQLiteLedgerStore


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_http(base_url: str, sqlite_path: str | Path, output: str | Path) -> dict:
    database = Path(sqlite_path)
    before_hash = _sha256(database)
    store = SQLiteLedgerStore(database)
    expected = LedgerReport(store.load()).summary(royalty_rate=0.10)
    expected_integrity = store.verify_integrity()
    errors: list[str] = []
    try:
        with urlopen(f"{base_url.rstrip('/')}/v1/reports", timeout=5) as response:
            api_version = response.headers.get("Content-Type")
            remote = json.load(response)
        if api_version != "application/json" or remote.get("api_version") != "v1":
            errors.append("report response is not a versioned JSON envelope")
        remote_report = remote.get("report")
        report_status = "verified" if remote_report == expected else "failed"
        if report_status == "failed":
            errors.append("HTTP report differs from SQLite recomputation")
    except Exception as exc:  # noqa: BLE001 - CLI must turn readback failures into a receipt
        report_status = "failed"
        errors.append(f"report readback error: {exc}")
        remote_report = None
    try:
        with urlopen(f"{base_url.rstrip('/')}/v1/integrity", timeout=5) as response:
            remote_integrity = json.load(response)
        integrity_status = "verified" if remote_integrity.get("status") == "verified" and remote_integrity == {"api_version": "v1", **expected_integrity} else "failed"
        if integrity_status == "failed":
            errors.append("HTTP integrity differs from SQLite verification")
    except Exception as exc:  # noqa: BLE001
        integrity_status = "failed"
        remote_integrity = None
        errors.append(f"integrity readback error: {exc}")
    try:
        with urlopen(f"{base_url.rstrip('/')}/", timeout=5) as response:
            dashboard = response.read().decode("utf-8")
            dashboard_type = response.headers.get("Content-Type")
        dashboard_status = "verified"
        for marker in ("Creator APIs report", "/v1/reports", "fixture_status"):
            if marker not in dashboard:
                dashboard_status = "failed"
                errors.append(f"dashboard missing marker: {marker}")
        if dashboard_type != "text/html; charset=utf-8":
            dashboard_status = "failed"
            errors.append("dashboard content type mismatch")
    except Exception as exc:  # noqa: BLE001 - see report readback handling above
        dashboard_status = "failed"
        errors.append(f"dashboard readback error: {exc}")
    after_hash = _sha256(database)
    if before_hash != after_hash:
        errors.append("HTTP readback mutated the SQLite database")
    verification = {
        "verification_version": "v1",
        "status": "verified" if not errors else "failed",
        "report_status": report_status,
        "integrity_status": integrity_status,
        "integrity": remote_integrity,
        "dashboard_status": dashboard_status,
        "database_sha256_before": before_hash,
        "database_sha256_after": after_hash,
        "report": remote_report,
        "errors": errors,
    }
    Path(output).write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"report={report_status} dashboard={dashboard_status} status={verification['status']}")
    return verification


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local HTTP report and dashboard readback.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--sqlite", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    verification = verify_http(args.base_url, args.sqlite, args.output)
    return 0 if verification["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
