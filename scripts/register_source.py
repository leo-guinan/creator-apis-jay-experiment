import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from creator_apis.sqlite_store import SQLiteLedgerStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Record an explicit local source status decision.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--status", choices=("synthetic", "approved_local_export", "rejected", "unknown"), required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--observed-at", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    decision = SQLiteLedgerStore(args.database).set_source_status(args.source_name, args.status, operator=args.operator, reason=args.reason, observed_at=args.observed_at)
    print(json.dumps(decision, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
