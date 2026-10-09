# Event batch receipt verification contract

`verify_event_batch.py` reopens the ledger and independently checks an import receipt.

Run:

    PYTHONPATH=src:scripts python3 scripts/verify_event_batch.py \
      --receipt /path/to/import.json

It recomputes the input hash and batch ID, rechecks the post-import integrity root and report digest, confirms applied source identities exist, and proves that dry-run or rejected-atomic receipts show no integrity or report change.

Editing a receipt field causes verification to fail. This is verification of local evidence, not a signature or an external witness.
