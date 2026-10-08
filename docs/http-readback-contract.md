# Independent local HTTP readback contract

Status: implemented localhost-only verification slice.

With the local server already running, verify the API and dashboard against a reopened SQLite ledger:

```bash
PYTHONPATH=src:scripts python3 scripts/verify_local_http.py \
  --base-url http://127.0.0.1:8080 \
  --sqlite examples/scenario-receipts/direct.sqlite \
  --output examples/scenario-receipts/http-verification.json
```

The verifier independently recomputes the expected report from SQLite, reads `GET /v1/reports`, and compares the two. It also reads `/`, checks the HTML content type and required report markers, and hashes the SQLite file before and after to prove that readback did not mutate local state.

It exits nonzero on report mismatch, dashboard failure, content-type mismatch, unavailable server, or database mutation. The output is a local verification receipt, not a deployment or production-readiness claim.
