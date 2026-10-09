"""Verify concurrent local writers serialize without corrupting the event chain."""
from __future__ import annotations

import argparse
import json
import multiprocessing
import tempfile
from pathlib import Path

from creator_apis.evidence import EvidenceLedger
from creator_apis.sqlite_store import SQLiteLedgerStore


def make_ledger() -> EvidenceLedger:
    return EvidenceLedger(fixture_status="synthetic", campaign_id="campaign:concurrency", experiment_id="experiment:concurrency")


def writer(path: str, event_id: str, result_queue) -> None:
    try:
        store = SQLiteLedgerStore(path)
        store.append_event({"event_id": event_id, "event_type": "observation", "session_id": f"session:{event_id}", "metadata": {"writer": event_id}})
        result_queue.put({"event_id": event_id, "status": "written"})
    except Exception as exc:  # subprocess result is the receipt, not an ignored failure
        result_queue.put({"event_id": event_id, "status": "failed", "error": repr(exc)})


def run(output: str | Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="creator-apis-concurrency-") as directory:
        database = Path(directory) / "ledger.sqlite"
        SQLiteLedgerStore.create(database, make_ledger())
        queue = multiprocessing.Queue()
        processes = [multiprocessing.Process(target=writer, args=(str(database), f"event:writer-{n}", queue)) for n in (1, 2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
        results = [queue.get(timeout=2) for _ in processes]
        store = SQLiteLedgerStore(database)
        integrity = store.verify_integrity()
        result = {"verification_version": "v1", "status": "verified" if all(item["status"] == "written" for item in results) and integrity["status"] == "verified" and integrity["event_count"] == 2 else "failed", "writers": sorted(results, key=lambda item: item["event_id"]), "integrity": integrity}
    destination = Path(output); destination.parent.mkdir(parents=True, exist_ok=True); destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"concurrency-writes: {result['status']}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify concurrent SQLite event writers.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run(args.output)["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
