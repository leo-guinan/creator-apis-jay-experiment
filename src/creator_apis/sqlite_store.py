import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence import EvidenceLedger

SCHEMA_VERSION = 4


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
        store._refresh_migration_receipt()
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
                CREATE TABLE IF NOT EXISTS import_batches (
                    batch_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    input_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    counts TEXT NOT NULL,
                    integrity_before TEXT NOT NULL,
                    integrity_after TEXT NOT NULL,
                    report_sha256_before TEXT NOT NULL,
                    report_sha256_after TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    errors TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sources (
                    source_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    batch_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_decisions (
                    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    previous_decision_hash TEXT,
                    decision_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    migration_id TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS migration_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    version_before INTEGER NOT NULL,
                    version_after INTEGER NOT NULL,
                    migration_ids TEXT NOT NULL,
                    event_root_before TEXT,
                    event_root_after TEXT,
                    decision_root_before TEXT,
                    decision_root_after TEXT,
                    report_sha256_before TEXT NOT NULL,
                    report_sha256_after TEXT NOT NULL,
                    ledger_identity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                """
            )
        with sqlite3.connect(self.path) as connection:
            version_before = connection.execute("PRAGMA user_version").fetchone()[0]
        self._migrate_schema()
        self._ensure_integrity_chain()
        if version_before < SCHEMA_VERSION:
            self._refresh_migration_receipt()

    def _migrate_schema(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            current_version = connection.execute("PRAGMA user_version").fetchone()[0]
            if current_version > SCHEMA_VERSION:
                raise ValueError(f"unsupported future schema version: {current_version}")
            event_root_before = self._event_root(connection)
            decision_root_before = self._decision_root(connection)
            report_before = self._report_digest()
            columns = {row[1] for row in connection.execute("PRAGMA table_info(source_decisions)")}
            for name, declaration in (("sequence", "INTEGER"), ("previous_decision_hash", "TEXT"), ("decision_hash", "TEXT")):
                if name not in columns:
                    connection.execute(f"ALTER TABLE source_decisions ADD COLUMN {name} {declaration}")
            rows = connection.execute("SELECT decision_id, source_name, previous_status, new_status, operator, reason, observed_at FROM source_decisions ORDER BY decision_id").fetchall()
            previous_hash = None
            for sequence, (decision_id, source_name, previous_status, new_status, operator, reason, observed_at) in enumerate(rows, start=1):
                canonical = {"sequence": sequence, "previous_decision_hash": previous_hash, "source_name": source_name, "previous_status": previous_status, "new_status": new_status, "operator": operator, "reason": reason, "observed_at": observed_at}
                decision_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                connection.execute("UPDATE source_decisions SET sequence = ?, previous_decision_hash = ?, decision_hash = ? WHERE decision_id = ?", (sequence, previous_hash, decision_hash, decision_id))
                previous_hash = decision_hash
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.execute("INSERT OR REPLACE INTO schema_migrations(version, migration_id, applied_at) VALUES (?, ?, ?)", (SCHEMA_VERSION, "schema:current", now))
            event_root_after = self._event_root(connection)
            decision_root_after = self._decision_root(connection)
            identity = self._ledger_identity(connection)
            connection.execute("INSERT OR REPLACE INTO migration_receipts(receipt_id, version_before, version_after, migration_ids, event_root_before, event_root_after, decision_root_before, decision_root_after, report_sha256_before, report_sha256_after, ledger_identity, status, applied_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (f"migration:{SCHEMA_VERSION}", current_version, SCHEMA_VERSION, json.dumps(["schema:current"]), event_root_before, event_root_after, decision_root_before, decision_root_after, report_before, report_before, identity, "applied", now))

    @staticmethod
    def _event_root(connection: sqlite3.Connection) -> str | None:
        row = connection.execute("SELECT payload FROM events ORDER BY rowid DESC LIMIT 1").fetchone()
        return json.loads(row[0]).get("event_hash") if row else None

    @staticmethod
    def _decision_root(connection: sqlite3.Connection) -> str | None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(source_decisions)")}
        if "decision_hash" not in columns:
            return None
        row = connection.execute("SELECT decision_hash FROM source_decisions ORDER BY sequence DESC, decision_id DESC LIMIT 1").fetchone()
        return row[0] if row and row[0] else None

    def _ledger_identity(self, connection: sqlite3.Connection | None = None) -> str:
        if connection is not None:
            metadata = {key: json.loads(value) for key, value in connection.execute("SELECT key, value FROM metadata")}
            if "fixture_status" not in metadata:
                return ""
            records = {key: json.loads(value) for key, value in connection.execute("SELECT record_id, payload FROM records")}
            identity = {"fixture_status": metadata["fixture_status"], "campaign_id": metadata.get("campaign_id"), "experiment_id": metadata.get("experiment_id"), "records": records}
            return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        try:
            ledger = self.load().export()
        except (KeyError, TypeError):
            return ""
        identity = {"fixture_status": ledger["fixture_status"], "campaign_id": ledger.get("campaign_id"), "experiment_id": ledger.get("experiment_id"), "records": ledger["records"]}
        return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _report_digest(self) -> str:
        from .reporting import LedgerReport
        try:
            report = LedgerReport(self.load()).summary(royalty_rate=0.10)
        except (KeyError, TypeError):
            return ""
        return hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def schema_status(self) -> dict[str, Any]:
        with sqlite3.connect(self.path) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            migrations = connection.execute("SELECT version, migration_id, applied_at FROM schema_migrations ORDER BY version").fetchall()
            receipts = connection.execute("SELECT receipt_id, version_before, version_after, migration_ids, event_root_before, event_root_after, decision_root_before, decision_root_after, report_sha256_before, report_sha256_after, ledger_identity, status, applied_at FROM migration_receipts ORDER BY applied_at").fetchall()
        return {"status": "ready" if version == SCHEMA_VERSION else "blocked", "version": version, "expected_version": SCHEMA_VERSION, "migrations": [dict(zip(("version", "migration_id", "applied_at"), row)) for row in migrations], "migration_receipts": [dict(zip(("receipt_id", "version_before", "version_after", "migration_ids", "event_root_before", "event_root_after", "decision_root_before", "decision_root_after", "report_sha256_before", "report_sha256_after", "ledger_identity", "status", "applied_at"), row)) for row in receipts]}

    def migration_receipts(self) -> list[dict[str, Any]]:
        return self.schema_status()["migration_receipts"]

    def _refresh_migration_receipt(self) -> None:
        with sqlite3.connect(self.path) as connection:
            receipt = connection.execute("SELECT receipt_id, version_before, version_after, migration_ids, event_root_before, decision_root_before, applied_at FROM migration_receipts ORDER BY applied_at DESC LIMIT 1").fetchone()
            if receipt is None:
                return
            event_root = self._event_root(connection)
            decision_root = self._decision_root(connection)
            report = self._report_digest()
            identity = self._ledger_identity(connection)
            connection.execute("UPDATE migration_receipts SET event_root_after = ?, decision_root_after = ?, report_sha256_before = ?, report_sha256_after = ?, ledger_identity = ? WHERE receipt_id = ?", (event_root, decision_root, report, report, identity, receipt[0]))

    @staticmethod
    def _canonical_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in event.items()
            if key not in {"sequence", "previous_event_hash", "event_hash"}
        }

    @classmethod
    def _chain_event(cls, event: dict[str, Any], sequence: int, previous_hash: str | None) -> dict[str, Any]:
        chained = dict(event)
        chained["sequence"] = sequence
        chained["previous_event_hash"] = previous_hash
        canonical = {"sequence": sequence, "previous_event_hash": previous_hash, "event": cls._canonical_event(event)}
        chained["event_hash"] = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return chained

    def _ensure_integrity_chain(self) -> None:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT event_id, payload FROM events ORDER BY rowid").fetchall()
            if not rows or all({"sequence", "previous_event_hash", "event_hash"} <= set(json.loads(payload)) for _, payload in rows):
                return
            previous_hash = None
            for sequence, (event_id, payload) in enumerate(rows, start=1):
                chained = self._chain_event(json.loads(payload), sequence, previous_hash)
                connection.execute("UPDATE events SET payload = ? WHERE event_id = ?", (json.dumps(chained, sort_keys=True), event_id))
                previous_hash = chained["event_hash"]

    def _write_ledger(self, connection: sqlite3.Connection, ledger: EvidenceLedger) -> None:
        payload = ledger.export()
        connection.execute("DELETE FROM metadata")
        connection.execute("DELETE FROM records")
        connection.execute("DELETE FROM events")
        connection.execute("DELETE FROM conversions")
        connection.execute("DELETE FROM import_batches")
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [(key, json.dumps(payload[key])) for key in ("fixture_status", "campaign_id", "experiment_id")],
        )
        connection.executemany(
            "INSERT INTO records(record_id, payload) VALUES (?, ?)",
            [(key, json.dumps(value, sort_keys=True)) for key, value in payload["records"].items()],
        )
        previous_hash = None
        chained_events = []
        for sequence, item in enumerate(payload["events"], start=1):
            chained = self._chain_event(item, sequence, previous_hash)
            chained_events.append((chained["event_id"], json.dumps(chained, sort_keys=True)))
            previous_hash = chained["event_hash"]
        connection.executemany(
            "INSERT INTO events(event_id, payload) VALUES (?, ?)", chained_events
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
        allowed = {"event_id", "event_type", "session_id", "route_id", "metadata", "campaign_id", "experiment_id", "observed_at", "source_name", "source_event_id", "batch_id"}
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
            "source_name": event.get("source_name"),
            "source_event_id": event.get("source_event_id"),
            "batch_id": event.get("batch_id"),
        }
        with sqlite3.connect(self.path) as connection:
            existing = connection.execute(
                "SELECT payload FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing is not None:
                existing_payload = json.loads(existing[0])
                if self._canonical_event(existing_payload) != self._canonical_event(normalized):
                    raise ValueError(f"event id conflict: {event_id}")
                return existing_payload, False
            row = connection.execute("SELECT payload FROM events ORDER BY rowid DESC LIMIT 1").fetchone()
            previous_hash = json.loads(row[0]).get("event_hash") if row else None
            sequence = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] + 1
            chained = self._chain_event(normalized, sequence, previous_hash)
            connection.execute(
                "INSERT INTO events(event_id, payload) VALUES (?, ?)",
                (event_id, json.dumps(chained, sort_keys=True)),
            )
        return chained, True

    def verify_integrity(self) -> dict[str, Any]:
        errors: list[str] = []
        previous_hash = None
        expected_sequence = 1
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT event_id, payload FROM events ORDER BY rowid").fetchall()
        for event_id, payload in rows:
            event = json.loads(payload)
            if event.get("event_id") != event_id:
                errors.append(f"event id mismatch: {event_id}")
            if event.get("sequence") != expected_sequence:
                errors.append(f"sequence mismatch: {event_id}")
            if event.get("previous_event_hash") != previous_hash:
                errors.append(f"previous hash mismatch: {event_id}")
            expected = self._chain_event(self._canonical_event(event), expected_sequence, previous_hash)["event_hash"]
            if event.get("event_hash") != expected:
                errors.append(f"event hash mismatch: {event_id}")
            previous_hash = event.get("event_hash")
            expected_sequence += 1
        return {
            "status": "verified" if not errors else "failed",
            "event_count": len(rows),
            "root_hash": previous_hash,
            "errors": errors,
        }

    def record_import_batch(self, manifest: dict[str, Any]) -> bool:
        required = {"batch_id", "source_name", "input_sha256", "status", "counts", "integrity_before", "integrity_after", "report_sha256_before", "report_sha256_after", "observed_at", "errors"}
        missing = required - set(manifest)
        if missing:
            raise ValueError(f"missing import manifest field: {sorted(missing)[0]}")
        with sqlite3.connect(self.path) as connection:
            existing = connection.execute("SELECT input_sha256 FROM import_batches WHERE batch_id = ?", (manifest["batch_id"],)).fetchone()
            if existing is not None:
                if existing[0] != manifest["input_sha256"]:
                    raise ValueError(f"import batch conflict: {manifest['batch_id']}")
                return False
            connection.execute(
                "INSERT INTO import_batches(batch_id, source_name, input_sha256, status, counts, integrity_before, integrity_after, report_sha256_before, report_sha256_after, observed_at, errors) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (manifest["batch_id"], manifest["source_name"], manifest["input_sha256"], manifest["status"], json.dumps(manifest["counts"], sort_keys=True), json.dumps(manifest["integrity_before"], sort_keys=True), json.dumps(manifest["integrity_after"], sort_keys=True), manifest["report_sha256_before"], manifest["report_sha256_after"], manifest["observed_at"], json.dumps(manifest["errors"], sort_keys=True)),
            )
            connection.execute(
                "INSERT INTO sources(source_name, status, first_seen, last_seen, batch_count) VALUES (?, ?, ?, ?, 1) ON CONFLICT(source_name) DO UPDATE SET last_seen = excluded.last_seen, batch_count = sources.batch_count + 1",
                (manifest["source_name"], manifest.get("source_status", "unknown"), manifest["observed_at"], manifest["observed_at"]),
            )
        return True

    def list_import_batches(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT batch_id, source_name, input_sha256, status, counts, integrity_before, integrity_after, report_sha256_before, report_sha256_after, observed_at, errors FROM import_batches ORDER BY observed_at, batch_id").fetchall()
        keys = ("batch_id", "source_name", "input_sha256", "status", "counts", "integrity_before", "integrity_after", "report_sha256_before", "report_sha256_after", "observed_at", "errors")
        result = []
        for row in rows:
            item = dict(zip(keys, row))
            for key in ("counts", "integrity_before", "integrity_after", "errors"):
                item[key] = json.loads(item[key])
            result.append(item)
        return result

    def list_sources(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT source_name, status, first_seen, last_seen, batch_count FROM sources ORDER BY source_name").fetchall()
        return [dict(zip(("source_name", "status", "first_seen", "last_seen", "batch_count"), row)) for row in rows]

    def set_source_status(self, source_name: str, status: str, *, operator: str, reason: str, observed_at: str) -> dict[str, Any]:
        allowed = {"synthetic", "approved_local_export", "rejected", "unknown"}
        if status not in allowed:
            raise ValueError(f"invalid source status: {status}")
        with sqlite3.connect(self.path) as connection:
            row = connection.execute("SELECT status FROM sources WHERE source_name = ?", (source_name,)).fetchone()
            previous = row[0] if row else "unknown"
            last = connection.execute("SELECT sequence, decision_hash FROM source_decisions ORDER BY sequence DESC LIMIT 1").fetchone()
            sequence = (last[0] if last else 0) + 1
            previous_hash = last[1] if last else None
            canonical = {"sequence": sequence, "previous_decision_hash": previous_hash, "source_name": source_name, "previous_status": previous, "new_status": status, "operator": operator, "reason": reason, "observed_at": observed_at}
            decision_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            if row is None:
                connection.execute("INSERT INTO sources(source_name, status, first_seen, last_seen, batch_count) VALUES (?, ?, ?, ?, 0)", (source_name, status, observed_at, observed_at))
            else:
                connection.execute("UPDATE sources SET status = ?, last_seen = ? WHERE source_name = ?", (status, observed_at, source_name))
            connection.execute("INSERT INTO source_decisions(source_name, previous_status, new_status, operator, reason, observed_at, sequence, previous_decision_hash, decision_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (source_name, previous, status, operator, reason, observed_at, sequence, previous_hash, decision_hash))
        return {"source_name": source_name, "previous_status": previous, "new_status": status, "operator": operator, "reason": reason, "observed_at": observed_at}

    def verify_source_decisions(self) -> dict[str, Any]:
        errors: list[str] = []
        previous_hash = None
        expected_sequence = 1
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT source_name, previous_status, new_status, operator, reason, observed_at, sequence, previous_decision_hash, decision_hash FROM source_decisions ORDER BY sequence").fetchall()
        source_status = {item["source_name"]: item["status"] for item in self.list_sources()}
        latest: dict[str, str] = {}
        for source_name, previous_status, new_status, operator, reason, observed_at, sequence, previous_decision_hash, decision_hash in rows:
            if sequence != expected_sequence or previous_decision_hash != previous_hash:
                errors.append(f"decision chain continuity mismatch: {source_name}")
            canonical = {"sequence": sequence, "previous_decision_hash": previous_decision_hash, "source_name": source_name, "previous_status": previous_status, "new_status": new_status, "operator": operator, "reason": reason, "observed_at": observed_at}
            expected_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            if decision_hash != expected_hash:
                errors.append(f"decision hash mismatch: {source_name}")
            if latest.get(source_name, "unknown") != previous_status:
                errors.append(f"decision transition mismatch: {source_name}")
            latest[source_name] = new_status
            previous_hash = decision_hash
            expected_sequence += 1
        for source_name, status in source_status.items():
            if status != latest.get(source_name, "unknown"):
                errors.append(f"source status differs from decision log: {source_name}")
        return {"status": "verified" if not errors else "failed", "decision_count": len(rows), "root_hash": previous_hash, "errors": errors}

    def list_source_decisions(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT decision_id, source_name, previous_status, new_status, operator, reason, observed_at FROM source_decisions ORDER BY decision_id").fetchall()
        return [dict(zip(("decision_id", "source_name", "previous_status", "new_status", "operator", "reason", "observed_at"), row)) for row in rows]

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
        with sqlite3.connect(self.path) as connection:
            existing_conversion = connection.execute(
                "SELECT payload FROM conversions WHERE conversion_id = ?", (conversion_id,)
            ).fetchone()
            if existing_conversion is not None:
                if existing_conversion[0] != conversion_encoded:
                    raise ValueError(f"conversion id conflict: {conversion_id}")
                return normalized, False
            row = connection.execute("SELECT payload FROM events ORDER BY rowid DESC LIMIT 1").fetchone()
            previous_hash = json.loads(row[0]).get("event_hash") if row else None
            sequence = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] + 1
            event = self._chain_event(event, sequence, previous_hash)
            event_encoded = json.dumps(event, sort_keys=True)
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
