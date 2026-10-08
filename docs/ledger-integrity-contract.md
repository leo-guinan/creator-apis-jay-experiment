# Local ledger integrity contract

Status: implemented localhost-only tamper-evidence slice.

SQLite events now carry:

- a monotonic sequence;
- the previous event hash;
- a canonical payload hash.

Verify a ledger directly:

```bash
PYTHONPATH=src:scripts python3 scripts/check_ledger_integrity.py \
  --sqlite examples/scenario-receipts/direct.sqlite \
  --output examples/scenario-receipts/integrity.json
```

The local API also exposes `GET /v1/integrity` when backed by SQLite. A valid chain returns `200`; a failed chain returns `503` with the detected errors. The endpoint is read-only.

The check detects payload edits, event reordering, sequence gaps, deleted events, previous-hash mismatches, and incorrect event hashes. The root hash identifies the verified event history.

This is tamper evidence, not tamper prevention. It does not provide signatures, key custody, remote attestation, or public auditability.
