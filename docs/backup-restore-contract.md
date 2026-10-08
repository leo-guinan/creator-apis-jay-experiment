# Local backup and restore contract

Status: implemented localhost-only durability slice.

Run:

```bash
PYTHONPATH=src:scripts python3 scripts/check_backup_restore.py \
  --output-dir examples/backup-recovery-receipts
```

The check populates a fresh SQLite ledger through the local HTTP route and conversion endpoints, creates a SQLite backup, restores that backup into a new file, and compares:

- the versioned report;
- direct attribution and synthetic royalty;
- the complete logical ledger export;
- source, backup, and restored artifact hashes.

The receipt is `backup-restore.json`. This proves bounded SQLite backup/restore fidelity. It does not prove off-machine backup delivery, encryption, retention, crash-consistency under power loss, or production disaster recovery.
