import argparse
from http.server import HTTPServer
from pathlib import Path

from creator_apis.api import ReportingAPI, create_handler
from creator_apis.store import LedgerStore
from creator_apis.sqlite_store import SQLiteLedgerStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the read-only Creator APIs report")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--ledger", default="examples/synthetic-ledger.json")
    source.add_argument("--sqlite", help="load a durable SQLite ledger instead of JSON")
    source.add_argument("--scenario-dir", help="serve fixed local scenarios from a directory of SQLite ledgers")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--audit-dir", help="directory containing backup/import/recovery receipts")
    args = parser.parse_args()
    dashboard = Path(__file__).resolve().parents[1] / "app" / "index.html"
    audit_paths = {}
    if args.audit_dir:
        audit_dir = Path(args.audit_dir)
        audit_paths = {
            "backup_receipt": audit_dir / "backup-receipt.json",
            "import_receipts": sorted(audit_dir.glob("import*.json")),
            "recovery_receipt": audit_dir / "repair-receipt.json",
        }
    if args.scenario_dir:
        directory = Path(args.scenario_dir)
        scenario_stores = {
            name: SQLiteLedgerStore(directory / f"{name}.sqlite")
            for name in ("direct", "ambiguous", "no-click")
        }
        api = ReportingAPI(store=scenario_stores["direct"], scenario_stores=scenario_stores, audit_paths=audit_paths)
    elif args.sqlite:
        api = ReportingAPI(store=SQLiteLedgerStore(Path(args.sqlite)), audit_paths=audit_paths)
    else:
        api = ReportingAPI(LedgerStore.load(Path(args.ledger)), audit_paths=audit_paths)
    dashboard = Path(__file__).resolve().parents[1] / "app" / "index.html"
    server = HTTPServer((args.host, args.port), create_handler(api, dashboard_path=dashboard))
    print(f"serving http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
