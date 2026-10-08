# Corruption pipeline contract

The local integrity boundary is tested with deliberate persisted-event corruption.

The checker changes one SQLite event payload, then verifies that:

1. direct SQLite integrity verification fails;
2. a SQLite backup and restore remain visibly invalid;
3. the HTTP integrity endpoint returns failure;
4. independent HTTP report readback fails even if the report itself can still be recomputed.

Run:

    PYTHONPATH=src:scripts python3 scripts/check_corruption_pipeline.py \
      --output examples/integrity-receipts/corruption-pipeline.json

The fixture is synthetic. This proves rejection and detection, not tamper prevention, external attestation, or production security.
