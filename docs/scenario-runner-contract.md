# Local synthetic scenario runner contract

Status: implemented localhost-only verification slice.

Run:

```bash
PYTHONPATH=src:scripts python3 scripts/run_synthetic_scenarios.py
```

The runner creates a clean SQLite ledger for each scenario and writes a JSON receipt beside it under `examples/scenario-receipts/`:

- `direct.json`: one route click, one conversion, direct attribution, 10,000 synthetic royalty cents;
- `ambiguous.json`: two valid route clicks in one session, unknown attribution, zero royalty;
- `no-click.json`: conversion without a route click, unknown attribution, zero royalty.

Each receipt includes `fixture_status: synthetic`, the local SQLite storage mode, the complete scoped report, attribution reason, and royalty totals. The SQLite databases are local ignored artifacts; the JSON receipts are the preserved review artifacts.

The runner does not contact external platforms, verify payment, publish content, or claim causal attribution. It exercises the existing evidence rules rather than introducing a scenario-specific attribution model.
