# Local HTTP scenario replay contract

Status: implemented localhost-only end-to-end verification slice.

Run:

```bash
PYTHONPATH=src:scripts python3 scripts/replay_http_scenarios.py
```

The harness creates a fresh SQLite ledger and drives all three cases through the actual local HTTP boundary:

```text
GET /r/<route_id>
→ Set-Cookie
→ POST /v1/conversions
→ GET /v1/reports
```

Cases:

- `direct`: one route redirect and one conversion; direct attribution;
- `ambiguous`: two route redirects in one session and one conversion; unknown attribution;
- `no-click`: conversion without a route redirect; unknown attribution.

Each JSON receipt in `examples/http-scenario-receipts/` records response status, redirect location, cookie creation, report comparison status, before/after database hashes, and the final report. The harness exits nonzero if the HTTP report differs from reopened SQLite state or if the readback changes the database.

This validates the user-shaped local mechanism. It does not establish payment, identity, causation, or production readiness.
