# Local scenario selector contract

Status: implemented localhost-only operator slice.

Generate the scenario SQLite artifacts, then serve the fixed scenario set:

```bash
PYTHONPATH=src:scripts python3 scripts/run_synthetic_scenarios.py
PYTHONPATH=src:scripts python3 scripts/serve_synthetic_report.py \
  --scenario-dir examples/scenario-receipts --port 8080
```

The dashboard reads `GET /v1/scenarios`, then selects one of the fixed names:

- `direct`
- `ambiguous`
- `no-click`

The selected report is read through `GET /v1/reports?scenario=<fixed-name>`. Scenario names are resolved from a fixed server-side map; the browser cannot request arbitrary filesystem paths. The selector is read-only and does not accept events or conversions.

Without `--scenario-dir`, the dashboard retains the existing default single-ledger behavior. The server remains bound to localhost and the underlying scenario SQLite databases remain local artifacts.
