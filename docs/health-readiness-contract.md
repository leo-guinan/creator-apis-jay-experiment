# Local health and readiness contract

Status: implemented localhost-only operator boundary.

`GET /healthz` returns a read-only readiness document:

```json
{
  "status": "ok",
  "api_version": "v1",
  "fixture_status": "synthetic",
  "storage": "sqlite",
  "scenarios": ["ambiguous", "direct", "no-click"],
  "read_only": true
}
```

Use the independent checker against a running local server:

```bash
PYTHONPATH=src:scripts python3 scripts/check_local_server.py \
  --base-url http://127.0.0.1:8080 \
  --expect-scenarios \
  --output examples/scenario-receipts/server-check.json
```

The checker verifies localhost scope, health status, synthetic fixture status, API version, read-only declaration, optional fixed scenario availability, report readback, dashboard content type/markers, and writes a JSON receipt. It exits nonzero on an unavailable or incompatible process.

This is a local operator check, not authentication, production monitoring, or a public health endpoint.
