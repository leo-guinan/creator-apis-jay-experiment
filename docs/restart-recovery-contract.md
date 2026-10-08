# Local restart recovery contract

Status: implemented localhost-only recovery slice.

Run:

```bash
PYTHONPATH=src:scripts python3 scripts/check_restart_recovery.py \
  --output-dir examples/recovery-receipts
```

The check creates a fresh SQLite ledger, drives a route click and synthetic conversion through HTTP, records the report, stops the server, starts a new server against the same SQLite file, and reads the health and report endpoints again.

It verifies:

- the route redirect returned `302`;
- the conversion returned `201`;
- the first report contained one conversion;
- the restarted server returned healthy;
- the restarted report retained direct attribution and the same report;
- the SQLite hash was unchanged by post-restart readback.

The output is `restart-recovery.json`. This proves local persistence across this bounded restart exercise; it does not prove backup durability, crash consistency under power loss, or production readiness.
