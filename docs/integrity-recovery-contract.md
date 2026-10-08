# Local integrity recovery contract

Recovery is a deliberate operator action. It is not automatic.

The operator must supply:

- the active SQLite database;
- a separately preserved backup whose integrity chain verifies;
- an output directory for the quarantine and repair receipt;
- an operator identifier and a reason.

Run:

    PYTHONPATH=src:scripts python3 scripts/recover_corrupt_ledger.py \
      --database examples/synthetic-ledger.sqlite \
      --verified-backup /path/to/verified-backup.sqlite \
      --output-dir examples/recovery-receipts \
      --operator leo \
      --reason "integrity failure during local verification"

The command refuses to proceed when:

- the active database is missing;
- the active database is already verified;
- the supplied backup is not verified.

On success it:

1. records the failed integrity result;
2. moves the database and SQLite sidecars into a quarantine directory;
3. restores the verified backup through SQLite backup APIs;
4. verifies the restored active database;
5. writes `repair-receipt.json` containing the repair ID, operator, reason, quarantine paths, before/backup/after integrity results, and UTC observation time.

This is local recovery, not forensic deletion or tamper prevention. The quarantined files must be retained until an operator decides otherwise.
