import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence import EvidenceLedger


class SQLiteLedgerStore:
    """Durable local store for ledger records, conversions, and append-only events."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self._initialize()

    @classmethod
    def create(cls, path: str | Path, ledger: EvidenceLedger):
        destination = Path(path)
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        store = cls.__new__(cls)
        store.path = destination
        store._initialize()
        with sqlite3.connect(store.path) as connection:
            store._write_ledger(connection, ledger)
        return store

    def _initialize(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversions (
                    conversion_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                """
            )

    def _write_ledger(self, connection: sqlite3.Connection, ledger: EvidenceLedger) -> None:
        payload = ledger.export()
        connection.execute("DELETE FROM metadata")
        connection.execute("DELETE FROM records")
        connection.execute("DELETE FROM events")
        connection.execute("DELETE FROM conversions")
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [(key, json.dumps(payload[key])) for key in ("fixture_status", "campaign_id", "experiment_id")],
        )
        connection.executemany(
            "INSERT INTO records(record_id, payload) VALUES (?, ?)",
            [(key, json.dumps(value, sort_keys=True)) for key, value in payload["records"].items()],
        )
        connection.executemany(
            "INSERT INTO events(event_id, payload) VALUES (?, ?)",
            [(item["event_id"], json.dumps(item, sort_keys=True)) for item in payload["events"]],
        )
        connection.executemany(
            "INSERT INTO conversions(conversion_id, payload) VALUES (?, ?)",
            [(key, json.dumps(value, sort_keys=True)) for key, value in payload["conversions"].items()],
        )

    def load(self) -> EvidenceLedger:
        with sqlite3.connect(self.path) as connection:
            metadata = {
                key: json.loads(value)
                for key, value in connection.execute("SELECT key, value FROM metadata")
            }
            ledger = EvidenceLedger(
                fixture_status=metadata["fixture_status"],
                campaign_id=metadata.get("campaign_id"),
                experiment_id=metadata.get("experiment_id"),
            )
            ledger.records = {
                record_id: json.loads(payload)
                for record_id, payload in connection.execute(
                    "SELECT record_id, payload FROM records ORDER BY record_id"
                )
            }
            ledger.events = [
                json.loads(payload)
                for _, payload in connection.execute(
                    "SELECT event_id, payload FROM events ORDER BY rowid"
                )
            ]
            ledger.conversions = {
                conversion_id: json.loads(payload)
                for conversion_id, payload in connection.execute(
                    "SELECT conversion_id, payload FROM conversions ORDER BY conversion_id"
                )
            }
            return ledger

    def append_event(self, event: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        allowed = {"event_id", "event_type", "session_id", "route_id", "metadata", "campaign_id", "experiment_id", "observed_at"}
        unknown = set(event) - allowed
        if unknown:
            raise ValueError(f"unknown event field: {sorted(unknown)[0]}")
        event_id = event.get("event_id")
        event_type = event.get("event_type")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("event_id is required")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type is required")
        ledger = self.load()
        route_id = event.get("route_id")
        route = ledger.records.get(route_id) if route_id is not None else None
        if route_id is not None and (route is None or route["record_type"] != "route"):
            raise ValueError(f"unknown route id: {route_id}")
        normalized = {
            "event_id": event_id,
            "event_type": event_type,
            "session_id": event.get("session_id"),
            "route_id": route_id,
            "metadata": dict(event.get("metadata") or {}),
            "observed_at": event.get("observed_at"),
            "fixture_status": ledger.fixture_status,
            "campaign_id": event.get("campaign_id") or (route and route["campaign_id"]) or ledger.campaign_id,
            "experiment_id": event.get("experiment_id") or (route and route["experiment_id"]) or ledger.experiment_id,
        }
        encoded = json.dumps(normalized, sort_keys=True)
        with sqlite3.connect(self.path) as connection:
            existing = connection.execute(
                "SELECT payload FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing is not None:
                if existing[0] != encoded:
                    raise ValueError(f"event id conflict: {event_id}")
                return normalized, False
            connection.execute(
                "INSERT INTO events(event_id, payload) VALUES (?, ?)",
                (event_id, encoded),
            )
        return normalized, True

    def append_conversion(self, conversion: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        allowed = {"conversion_id", "session_id", "amount_cents", "purchase_event_id", "campaign_id", "experiment_id"}
        unknown = set(conversion) - allowed
        if unknown:
            raise ValueError(f"unknown conversion field: {sorted(unknown)[0]}")
        conversion_id = conversion.get("conversion_id")
        session_id = conversion.get("session_id")
        amount_cents = conversion.get("amount_cents")
        if not isinstance(conversion_id, str) or not conversion_id:
            raise ValueError("conversion_id is required")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id is required")
        if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
            raise ValueError("amount_cents must be an integer")
        if amount_cents < 0:
            raise ValueError("amount_cents cannot be negative")
        ledger = self.load()
        purchase_event_id = conversion.get("purchase_event_id") or f"event:purchase-{conversion_id}"
        if not isinstance(purchase_event_id, str) or not purchase_event_id:
            raise ValueError("purchase_event_id must be a non-empty string")
        normalized = {
            "conversion_id": conversion_id,
            "session_id": session_id,
            "amount_cents": amount_cents,
            "purchase_event_id": purchase_event_id,
            "fixture_status": ledger.fixture_status,
            "campaign_id": conversion.get("campaign_id") or ledger.campaign_id,
            "experiment_id": conversion.get("experiment_id") or ledger.experiment_id,
        }
        event = {
            "event_id": purchase_event_id,
            "event_type": "purchase",
            "session_id": session_id,
            "route_id": None,
            "metadata": {"conversion_id": conversion_id, "amount_cents": amount_cents},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "fixture_status": ledger.fixture_status,
            "campaign_id": normalized["campaign_id"],
            "experiment_id": normalized["experiment_id"],
        }
        conversion_encoded = json.dumps(normalized, sort_keys=True)
        event_encoded = json.dumps(event, sort_keys=True)
        with sqlite3.connect(self.path) as connection:
            existing_conversion = connection.execute(
                "SELECT payload FROM conversions WHERE conversion_id = ?", (conversion_id,)
            ).fetchone()
            if existing_conversion is not None:
                if existing_conversion[0] != conversion_encoded:
                    raise ValueError(f"conversion id conflict: {conversion_id}")
                return normalized, False
            existing_event = connection.execute(
                "SELECT payload FROM events WHERE event_id = ?", (purchase_event_id,)
            ).fetchone()
            if existing_event is not None and existing_event[0] != event_encoded:
                raise ValueError(f"event id conflict: {purchase_event_id}")
            if existing_event is None:
                connection.execute(
                    "INSERT INTO events(event_id, payload) VALUES (?, ?)",
                    (purchase_event_id, event_encoded),
                )
            connection.execute(
                "INSERT INTO conversions(conversion_id, payload) VALUES (?, ?)",
                (conversion_id, conversion_encoded),
            )
        return normalized, True
