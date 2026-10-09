# SQLite schema migration contract

SQLite schema changes are versioned through `schema_migrations` and `PRAGMA user_version`. Opening a database applies the current idempotent migration transaction, backfills decision-chain fields when necessary, and records the current schema version.

`SQLiteLedgerStore.schema_status()` reports version, expected version, and migration records. Each migration also records a durable receipt containing the before/after event root, source-decision root, report digest, and ledger identity. `scripts/verify_migration_receipt.py` reads the database without running migrations and independently rejects edited or wrong receipts. `/healthz` includes the schema status.

Migration acceptance requires:

- an older valid database opens at the current schema version;
- a current database is a no-op;
- event integrity and report state are preserved;
- partially incompatible schema states fail rather than silently pretending to be current;
- edited and wrong-database receipts are rejected by the independent verifier.

Schema migration is local-only. It does not publish data, change attribution rules, or authorize external ingestion. Local writes use SQLite WAL mode, a bounded busy timeout, and `BEGIN IMMEDIATE` for event, conversion, source-decision, and import-manifest mutations. `scripts/check_concurrent_writes.py` verifies two writer processes serialize without breaking the event chain.
