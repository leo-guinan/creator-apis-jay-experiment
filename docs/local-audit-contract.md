# Local operator audit contract

`check_local_audit.py` reconciles the active SQLite ledger with integrity, backup, import, and recovery receipts.

    PYTHONPATH=src:scripts python3 scripts/check_local_audit.py \
      --database examples/synthetic-ledger.sqlite \
      --backup-receipt /path/to/backup-receipt.json \
      --import-receipt /path/to/import-receipt.json \
      --recovery-receipt /path/to/repair-receipt.json \
      --output /path/to/audit.json

Statuses:

- `ready`: integrity and configured receipts agree, with no warnings;
- `degraded`: the active ledger is valid but a non-fatal operational condition exists, such as no configured backup;
- `blocked`: active integrity failed, a backup identity/hash/root mismatched, a recovery receipt is invalid, or an import report no longer matches the active ledger.

The same read-only result is available at `GET /v1/audit`. Pass `--audit-dir` to the local server to discover `backup-receipt.json`, `import*.json`, and `repair-receipt.json` from one directory. The dashboard displays the audit status without adding a write path.

The state matrix checker exercises all three states and HTTP status semantics:

    PYTHONPATH=src:scripts python3 scripts/check_audit_states.py \
      --output examples/integrity-receipts/audit-states.json

It proves `ready` and `degraded` return HTTP 200 while `blocked` returns HTTP 503.
