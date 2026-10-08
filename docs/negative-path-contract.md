# Local negative-path contract

Status: implemented localhost-only defensive verification slice.

Run:

```bash
PYTHONPATH=src:scripts python3 scripts/check_negative_paths.py \
  --output-dir examples/negative-path-receipts
```

The check establishes one valid synthetic baseline, then verifies that these requests fail with the intended status without changing the logical SQLite ledger state:

- unknown scenario: `400`;
- unknown route redirect: `404`;
- conversion without a session: `400`;
- negative conversion amount: `400`;
- unknown conversion field: `400`;
- malformed JSON: `400`;
- event with unknown route: `400`;
- conflicting conversion ID: `400`.

The receipt preserves each expected/actual status and before/after logical ledger hashes. This is defensive local validation, not an authorization or abuse-control system.
