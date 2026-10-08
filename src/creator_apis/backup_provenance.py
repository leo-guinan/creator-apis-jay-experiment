import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .reporting import LedgerReport
from .sqlite_store import SQLiteLedgerStore


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ledger_identity(store: SQLiteLedgerStore) -> str:
    ledger = store.load().export()
    identity = {
        "fixture_status": ledger["fixture_status"],
        "campaign_id": ledger.get("campaign_id"),
        "experiment_id": ledger.get("experiment_id"),
        "records": ledger["records"],
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def report_digest(store: SQLiteLedgerStore) -> str:
    report = LedgerReport(store.load()).summary(royalty_rate=0.10)
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def checkpoint(store: SQLiteLedgerStore) -> None:
    with sqlite3.connect(store.path) as connection:
        connection.execute("PRAGMA wal_checkpoint(FULL)")
