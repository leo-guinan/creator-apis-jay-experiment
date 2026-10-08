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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if args.sqlite:
        api = ReportingAPI(store=SQLiteLedgerStore(Path(args.sqlite)))
    else:
        api = ReportingAPI(LedgerStore.load(Path(args.ledger)))
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
