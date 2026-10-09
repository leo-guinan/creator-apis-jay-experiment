import hashlib
import json
from pathlib import Path
from typing import Iterable

from .backup_provenance import ledger_identity, report_digest, sha256_file
from .sqlite_store import SQLiteLedgerStore


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_local_state(store: SQLiteLedgerStore, *, backup_receipt: Path | None = None, import_receipts: Iterable[Path] = (), recovery_receipt: Path | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    integrity = store.verify_integrity()
    if integrity["status"] != "verified":
        errors.append("active ledger integrity failed")
    identity = ledger_identity(store)
    current_report = report_digest(store)
    backup = None
    if backup_receipt is None or not backup_receipt.exists():
        warnings.append("no verified backup receipt configured")
    else:
        try:
            backup = _load(backup_receipt)
            backup_path = Path(backup["backup_path"])
            backup_store = SQLiteLedgerStore(backup_path)
            backup_integrity = backup_store.verify_integrity()
            if backup.get("backup_sha256") != sha256_file(backup_path):
                errors.append("backup file hash mismatch")
            if backup.get("backup_integrity") != backup_integrity:
                errors.append("backup integrity receipt mismatch")
            if backup.get("ledger_identity") != identity:
                errors.append("backup ledger identity mismatch")
            if backup_integrity != integrity:
                warnings.append("backup is valid but not current")
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"backup receipt invalid: {exc}")
    imports = sorted((path for path in import_receipts if path.exists()), key=lambda path: path.stat().st_mtime, reverse=True)
    manifests = store.list_import_batches()
    manifest_by_id = {item["batch_id"]: item for item in manifests}
    event_batch_ids = {event.get("batch_id") for event in store.load().events if isinstance(event.get("batch_id"), str)}
    for batch_id in sorted(event_batch_ids - set(manifest_by_id)):
        errors.append(f"event references unknown import batch: {batch_id}")
    for manifest in manifests:
        linked = sum(1 for event in store.load().events if event.get("batch_id") == manifest["batch_id"])
        if manifest["status"] == "applied" and linked != manifest["counts"].get("applied"):
            errors.append(f"import manifest event count mismatch: {manifest['batch_id']}")
        if manifest["status"] == "rejected_atomic" and linked != 0:
            errors.append(f"rejected batch has linked events: {manifest['batch_id']}")
    receipt_batch_ids = set()
    latest_import = None
    for path in imports:
        try:
            external = _load(path)
            batch_id = external["batch_id"]
            receipt_batch_ids.add(batch_id)
            manifest = manifest_by_id.get(batch_id)
            if manifest is None:
                errors.append(f"import receipt has no SQLite manifest: {batch_id}")
            elif external.get("manifest", {}).get("input_sha256") != manifest["input_sha256"] or external.get("manifest", {}).get("counts") != manifest["counts"]:
                errors.append(f"import receipt differs from SQLite manifest: {batch_id}")
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"import receipt invalid: {exc}")
    if manifests and imports and set(manifest_by_id) - receipt_batch_ids:
        warnings.append("some SQLite import manifests have no external receipt")
    if imports:
        latest_import = _load(imports[0])
        if latest_import.get("status") == "applied" and latest_import.get("report_sha256_after") != current_report:
            errors.append("latest import report digest differs from active report")
        if latest_import.get("status") in {"rejected_atomic", "dry_run"} and latest_import.get("integrity_before") != latest_import.get("integrity_after"):
            errors.append("non-applied import changed integrity")
    else:
        warnings.append("no import receipt configured")
    recovery = None
    if recovery_receipt is not None and recovery_receipt.exists():
        recovery = _load(recovery_receipt)
        if recovery.get("status") != "repaired" or recovery.get("integrity_after", {}).get("status") != "verified":
            errors.append("latest recovery receipt is not verified")
    status = "blocked" if errors else "degraded" if warnings else "ready"
    return {
        "audit_version": "v1",
        "status": status,
        "fixture_status": store.load().fixture_status,
        "integrity": integrity,
        "ledger_identity": identity,
        "report_sha256": current_report,
        "backup": backup,
        "latest_import": latest_import,
        "manifests": manifests,
        "sources": store.list_sources(),
        "recovery": recovery,
        "warnings": warnings,
        "errors": errors,
    }
