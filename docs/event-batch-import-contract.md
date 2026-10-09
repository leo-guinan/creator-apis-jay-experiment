# Local event batch import contract

`import_event_batch.py` imports a versioned JSONL event batch into the local SQLite ledger. Each line must contain `source_name` and `source_event_id`; the importer derives a deterministic local event ID from that pair and preserves both source identifiers.

Dry run:

    PYTHONPATH=src:scripts python3 scripts/import_event_batch.py \
      --database examples/synthetic-ledger.sqlite \
      --input /path/to/events.jsonl \
      --receipt /path/to/dry-run.json

Apply:

    PYTHONPATH=src:scripts python3 scripts/import_event_batch.py \
      --database examples/synthetic-ledger.sqlite \
      --input /path/to/events.jsonl \
      --receipt /path/to/import.json \
      --apply

The importer classifies accepted, duplicate, and rejected rows and records malformed lines and rejection reasons. Apply uses a staged SQLite copy and replaces the active database only after every row validates and applies, so a mixed valid/invalid batch is rejected atomically.

A repeated identical batch is idempotent: the first run applies new source events and the second records duplicates without changing the event count, integrity root, or report digest. Conflicting reuse of a source identity is rejected.

The receipt includes the input hash, batch ID, counts, outcomes, integrity roots, and report digests before and after. Synthetic fixtures remain synthetic; this is not a live platform adapter.
