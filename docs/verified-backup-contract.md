# Verified backup provenance contract

`create_verified_backup.py` creates a SQLite backup only from a ledger whose integrity chain verifies. It checkpoints WAL state, copies through SQLite backup APIs, re-verifies the copy, and writes a provenance receipt.

The receipt binds the backup to:

- source and backup file hashes;
- event count and root hash;
- campaign and experiment IDs;
- a stable ledger identity derived from fixture metadata and records;
- a deterministic report digest.

Run:

    PYTHONPATH=src:scripts python3 scripts/create_verified_backup.py \
      --source examples/synthetic-ledger.sqlite \
      --backup /path/to/verified-backup.sqlite \
      --receipt /path/to/verified-backup.json

Recovery requires this receipt. It rejects a backup whose file hash, integrity result, receipt path, or ledger identity does not match the active ledger. A valid backup from another campaign is therefore not accepted as a recovery source.

This is local provenance, not cryptographic signing or immutable off-machine storage.
