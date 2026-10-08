# Independent scenario receipt verification

Status: implemented localhost-only verification slice.

Run after generating scenario artifacts:

```bash
PYTHONPATH=src:scripts python3 scripts/run_synthetic_scenarios.py
PYTHONPATH=src:scripts python3 scripts/verify_synthetic_scenarios.py
```

`verify_synthetic_scenarios.py` is a separate readback process. It reopens each scenario SQLite database, recomputes `LedgerReport`, compares that report to the preserved JSON receipt, computes SHA-256 hashes for both artifacts, and writes `verification.json`.

The verifier exits nonzero if a receipt is missing, a database cannot be reopened, the fixture is not synthetic, or the recomputed report differs. It does not trust the runner's in-memory ledger or regenerate the expected report from the receipt itself.

Current local verification:

- `direct`: verified;
- `ambiguous`: verified;
- `no-click`: verified;
- 3 of 3 scenarios verified.

The hashes identify the exact local artifacts checked. They are evidence of consistency between the receipt and SQLite state, not proof of real-world payment, customer identity, causality, or economics.
