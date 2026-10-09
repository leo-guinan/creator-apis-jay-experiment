"""Import a local JSONL event batch with dry-run and atomic apply modes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from creator_apis.backup_provenance import report_digest
from creator_apis.sqlite_store import SQLiteLedgerStore


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _source_equivalent(value: dict, event: dict) -> bool:
    ignored = {"sequence", "previous_event_hash", "event_hash", "fixture_status"}
    return _canonical({k: v for k, v in value.items() if k not in ignored}) == _canonical({k: v for k, v in event.items() if k not in ignored})


def _load_batch(path: Path) -> tuple[list[dict], list[str]]:
    events: list[dict] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: malformed JSON ({exc.msg})")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {line_number}: event must be an object")
            continue
        value["_line_number"] = line_number
        events.append(value)
    return events, errors


def _prepare(store: SQLiteLedgerStore, events: list[dict], parse_errors: list[str], batch_id: str) -> tuple[list[dict], list[dict], list[str]]:
    ledger = store.load()
    prepared: list[dict] = []
    outcomes: list[dict] = []
    errors = list(parse_errors)
    existing = {(
        event.get("source_name"), event.get("source_event_id")
    ): event for event in ledger.events if event.get("source_name") and event.get("source_event_id")}
    seen: dict[tuple[str, str], dict] = {}
    for raw in events:
        line = raw.pop("_line_number")
        source_name = raw.get("source_name")
        source_event_id = raw.get("source_event_id")
        if not isinstance(source_name, str) or not source_name or not isinstance(source_event_id, str) or not source_event_id:
            errors.append(f"line {line}: source_name and source_event_id are required")
            outcomes.append({"line": line, "outcome": "rejected", "reason": "missing_source_identity"})
            continue
        key = (source_name, source_event_id)
        event = dict(raw)
        event["event_id"] = f"import:{source_name}:{source_event_id}"
        event["batch_id"] = batch_id
        event.setdefault("metadata", {})
        event.setdefault("session_id", None)
        event.setdefault("route_id", None)
        event.setdefault("observed_at", None)
        event.setdefault("campaign_id", ledger.campaign_id)
        event.setdefault("experiment_id", ledger.experiment_id)
        if event.get("campaign_id") != ledger.campaign_id or event.get("experiment_id") != ledger.experiment_id:
            errors.append(f"line {line}: event is out of scope")
            outcomes.append({"line": line, "outcome": "rejected", "reason": "out_of_scope"})
            continue
        prior = seen.get(key) or existing.get(key)
        if prior is not None:
            if _source_equivalent(prior, event):
                outcomes.append({"line": line, "outcome": "duplicate", "source_name": source_name, "source_event_id": source_event_id})
            else:
                errors.append(f"line {line}: conflicting source event identity")
                outcomes.append({"line": line, "outcome": "rejected", "reason": "conflicting_source_event_id"})
            continue
        seen[key] = event
        prepared.append(event)
        outcomes.append({"line": line, "outcome": "accepted", "source_name": source_name, "source_event_id": source_event_id})
    return prepared, outcomes, errors


def import_batch(database: str | Path, input_path: str | Path, receipt_path: str | Path, *, apply: bool) -> dict:
    database = Path(database)
    input_path = Path(input_path)
    receipt_path = Path(receipt_path)
    store = SQLiteLedgerStore(database)
    before_integrity = store.verify_integrity()
    before_report = report_digest(store)
    input_hash = _file_hash(input_path)
    batch_id = f"batch:{input_path.stem}:{input_hash[:16]}"
    events, parse_errors = _load_batch(input_path)
    prepared, outcomes, errors = _prepare(store, events, parse_errors, batch_id)
    status = "rejected" if errors else "dry_run" if not apply else "applied"
    applied = 0
    if apply and not errors:
        with tempfile.TemporaryDirectory(dir=database.parent) as temporary:
            staged = Path(temporary) / database.name
            with sqlite3.connect(database) as source, sqlite3.connect(staged) as target:
                source.backup(target)
            staged_store = SQLiteLedgerStore(staged)
            for event in prepared:
                _, created = staged_store.append_event(event)
                applied += int(created)
            with sqlite3.connect(staged) as source, sqlite3.connect(database) as target:
                source.backup(target)
    after_store = SQLiteLedgerStore(database)
    after_integrity = after_store.verify_integrity()
    after_report = report_digest(after_store)
    counts = {name: sum(1 for outcome in outcomes if outcome["outcome"] == name) for name in ("accepted", "duplicate", "rejected")}
    counts["rejected"] += len(parse_errors)
    if errors and apply:
        status = "rejected_atomic"
    receipt = {
        "receipt_version": "v1",
        "batch_id": batch_id,
        "status": status,
        "fixture_status": after_store.load().fixture_status,
        "apply_requested": apply,
        "input_path": str(input_path),
        "input_sha256": _file_hash(input_path),
        "database": str(database),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "counts": {**counts, "applied": applied},
        "errors": errors,
        "outcomes": outcomes,
        "integrity_before": before_integrity,
        "integrity_after": after_integrity,
        "report_sha256_before": before_report,
        "report_sha256_after": after_report,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    source_names = sorted({event.get("source_name") for event in events if event.get("source_name")})
    manifest = {
        "batch_id": batch_id,
        "source_name": source_names[0] if len(source_names) == 1 else "multiple",
        "source_status": "synthetic",
        "input_sha256": input_hash,
        "status": status,
        "counts": receipt["counts"],
        "integrity_before": before_integrity,
        "integrity_after": after_integrity,
        "report_sha256_before": before_report,
        "report_sha256_after": after_report,
        "observed_at": receipt["observed_at"],
        "errors": errors,
    }
    after_store.record_import_batch(manifest)
    receipt["manifest"] = manifest
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or atomically apply a local JSONL event batch.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = import_batch(args.database, args.input, args.receipt, apply=args.apply)
    print(f"batch={result['batch_id']} status={result['status']} counts={result['counts']}")
    return 0 if result["status"] in {"dry_run", "applied", "rejected_atomic"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
