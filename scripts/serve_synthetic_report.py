import argparse
from http.server import HTTPServer
from pathlib import Path

from creator_apis.api import ReportingAPI, create_handler
from creator_apis.store import LedgerStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the read-only Creator APIs report")
    parser.add_argument("--ledger", default="examples/synthetic-ledger.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    ledger = LedgerStore.load(Path(args.ledger))
    server = HTTPServer((args.host, args.port), create_handler(ReportingAPI(ledger)))
    print(f"serving http://{args.host}:{args.port}/v1/reports")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
