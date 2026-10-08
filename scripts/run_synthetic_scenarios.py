import argparse
import json
from pathlib import Path
from typing import Callable

from build_synthetic_receipt import build_fixture
from creator_apis.reporting import LedgerReport
from creator_apis.sqlite_store import SQLiteLedgerStore


AMOUNT_CENTS = 100_000


def _fresh_store(path: Path) -> SQLiteLedgerStore:
    ledger, _ = build_fixture()
    ledger.events.clear()
    ledger.conversions.clear()
    return SQLiteLedgerStore.create(path, ledger)


def _direct(store: SQLiteLedgerStore) -> None:
    store.append_event({
        "event_id": "event:scenario-direct-click",
        "event_type": "route_click",
        "session_id": "session:scenario-direct",
        "route_id": "route:jay-youtube-001",
        "observed_at": "2026-01-01T00:00:00+00:00",
    })
    store.append_conversion({
        "conversion_id": "conversion:scenario-direct",
        "session_id": "session:scenario-direct",
        "amount_cents": AMOUNT_CENTS,
    })


def _ambiguous(store: SQLiteLedgerStore) -> None:
    for event_id, route_id in (
        ("event:scenario-ambiguous-youtube", "route:jay-youtube-001"),
        ("event:scenario-ambiguous-x", "route:jay-x-001"),
    ):
        store.append_event({
            "event_id": event_id,
            "event_type": "route_click",
            "session_id": "session:scenario-ambiguous",
            "route_id": route_id,
            "observed_at": "2026-01-01T00:00:00+00:00",
        })
    store.append_conversion({
        "conversion_id": "conversion:scenario-ambiguous",
        "session_id": "session:scenario-ambiguous",
        "amount_cents": AMOUNT_CENTS,
    })


def _no_click(store: SQLiteLedgerStore) -> None:
    store.append_conversion({
        "conversion_id": "conversion:scenario-no-click",
        "session_id": "session:scenario-no-click",
        "amount_cents": AMOUNT_CENTS,
    })


SCENARIOS: dict[str, Callable[[SQLiteLedgerStore], None]] = {
    "direct": _direct,
    "ambiguous": _ambiguous,
    "no-click": _no_click,
}


def run_scenarios(output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    receipts: list[Path] = []
    for name, scenario in SCENARIOS.items():
        sqlite_path = destination / f"{name}.sqlite"
        if sqlite_path.exists():
            sqlite_path.unlink()
        for suffix in ("-shm", "-wal"):
            sidecar = Path(f"{sqlite_path}{suffix}")
            if sidecar.exists():
                sidecar.unlink()
        store = _fresh_store(sqlite_path)
        scenario(store)
        report = LedgerReport(SQLiteLedgerStore(sqlite_path).load()).summary(royalty_rate=0.10)
        receipt = {
            "receipt_version": "v1",
            "scenario": name,
            "fixture_status": "synthetic",
            "storage": {"mode": "local_sqlite", "database": sqlite_path.name},
            "report": report,
        }
        receipt_path = destination / f"{name}.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipts.append(receipt_path)
        attribution = report["attributions"][0]
        print(f"{name}: classification={attribution['classification']} royalty_cents={report['royalty']['accrued_amount_cents']}")
    return receipts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local synthetic attribution scenarios.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "examples" / "scenario-receipts",
    )
    args = parser.parse_args()
    for path in run_scenarios(args.output_dir):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
