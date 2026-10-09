# Creator APIs — Jay Evidence Experiment

This repository is a bounded, public source-and-documentation experiment for Creator APIs. The runtime is intentionally local-only. It starts from the approved Jay + Leo conversation and tests whether a human contribution can be traced through derived content to a directly attributable value event.

## Current status

Implemented and verified locally:

`campaign/experiment → contributor → source → content block → artifact → placement(s) → route click → purchase → direct attribution → synthetic royalty accrual`

The implementation is a local Python reference slice. It does not publish to external platforms, process payments, settle royalties, establish validated economics, or expose a public runtime.

## Run the verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 scripts/build_synthetic_receipt.py
PYTHONPATH=src:scripts python3 scripts/report_synthetic_fixture.py
PYTHONPATH=src:scripts python3 scripts/persist_synthetic_fixture.py
PYTHONPATH=src:scripts python3 scripts/serve_synthetic_report.py --port 8080
PYTHONPATH=src:scripts python3 scripts/persist_synthetic_sqlite.py
PYTHONPATH=src:scripts python3 scripts/serve_synthetic_report.py --sqlite examples/synthetic-ledger.sqlite --port 8080
PYTHONPATH=src:scripts python3 scripts/run_synthetic_scenarios.py
PYTHONPATH=src:scripts python3 scripts/verify_synthetic_scenarios.py
```

The generated receipt is `examples/synthetic-evidence-receipt.json`. It is explicitly marked `fixture_status: synthetic` and includes YouTube and X placement/route records under one campaign and experiment.
The generated report is `examples/synthetic-report.json`; it is a read-only summary of the same scoped fixture.
The persisted fixtures are `examples/synthetic-ledger.json` and a local ignored `examples/synthetic-ledger.sqlite`. The API serves `GET /v1/reports` from either source, accepts `POST /v1/events` and `POST /v1/conversions` when backed by SQLite, and tracks local route redirects at `GET /r/<route_id>`.

## Documentation

- `docs/project-start.md` — source boundary, work completed, and next slice.
- `docs/v0-evidence-ledger-contract.md` — record model and direct-attribution rules.
- `docs/reporting-contract.md` — read-only report shape, filters, and boundaries.
- `docs/event-ingestion-contract.md` — durable event write boundary and idempotence rules.
- `docs/dashboard-contract.md` — local read-only dashboard surface and security boundary.
- `docs/routing-contract.md` — local tracked-route redirect and session boundary.
- `docs/conversion-contract.md` — local synthetic conversion and purchase-event boundary.
- `docs/scenario-runner-contract.md` — preserved direct, ambiguous, and no-click report receipts.
- `docs/scenario-verification-contract.md` — independent SQLite/report readback and artifact hashes.
- `docs/http-readback-contract.md` — independent localhost API/dashboard readback.
- `docs/http-scenario-replay-contract.md` — end-to-end localhost route/conversion/report replay.
- `docs/operator-scenario-selector.md` — fixed local read-only scenario selection in the dashboard.
- `docs/health-readiness-contract.md` — local health endpoint and independent server checker.
- `docs/restart-recovery-contract.md` — HTTP observation/report recovery across a local restart.
- `docs/negative-path-contract.md` — local malformed, conflict, and unknown-resource checks.
- `docs/backup-restore-contract.md` — bounded local SQLite backup and restore fidelity.
- `docs/ledger-integrity-contract.md` — tamper-evident local event hash chain.
- `docs/corruption-pipeline-contract.md` — deliberate corruption rejection across SQLite, backup/restore, and HTTP readback.
- `docs/integrity-recovery-contract.md` — operator-controlled quarantine, verified restore, and repair receipt.
- `docs/verified-backup-contract.md` — backup identity, hashes, roots, and provenance receipts.
- `docs/event-batch-import-contract.md` — local JSONL ingestion, dry runs, idempotency, and atomic apply.
- `docs/event-batch-verification-contract.md` — independent batch receipt and SQLite readback verification.
- `docs/local-audit-contract.md` — reconciled operator status across integrity, backups, imports, and recovery.
- `docs/import-manifest-contract.md` — durable SQLite import manifests and read-only import history.
- `docs/source-status-policy-contract.md` — explicit source approval, rejection, and decision history.
- `docs/decisions/0001-local-runtime.md` — accepted local-only runtime decision and future promotion gate.
- `docs/jay-conversation-ledger.md` — source-derived observations, implications, and falsifiers.
- `docs/sources/creator-apis-initial-architecture.md` — supplied architecture brief.
- `docs/transcripts/` — approved timestamped transcript artifacts from the Jay recording.

## Privacy and provenance boundary

The raw recording remains at its original local path and is not copied into this repository. Leo confirmed that Jay approved recording and publication to the YouTube channel; the transcript is therefore included as a narrower public, source-linked working artifact. Source-derived observations remain labeled, and synthetic fixture output must not be read as a real payment, customer conversion, platform publication, or settled royalty.

## Implemented durable ingestion slice

Campaign and experiment identifiers now propagate through records, events, conversions, and attribution results. Multiple placements/routes are supported, and ambiguous same-session route clicks remain `unknown` rather than being assigned to a channel by guesswork.

`LedgerReport` provides scoped counts, placement/channel coverage, event counts, conversion classifications, evidence traces, and directly attributable royalty totals without mutating the ledger. `LedgerStore` persists and reloads JSON exports. `SQLiteLedgerStore` provides durable append-only event storage with WAL journaling. `POST /v1/events` is idempotent for identical replays, rejects conflicting event IDs and unknown routes, and `GET /v1/reports` reloads from SQLite on every request.

Malformed paths, query parameters, and event payloads return bounded errors; no external platform or payment integration is implied.

The local server also serves the browser dashboard at `/`. It is a read-only client of `GET /v1/reports`; it does not write events or replace the attribution model. Keep it bound to `127.0.0.1`.

`GET /r/<route_id>` is the first action-shaped boundary. It records a timestamped `route_click`, preserves a localhost session cookie, and redirects to the configured destination. It does not claim a conversion.

`POST /v1/conversions` is the local synthetic conversion boundary. It uses the route session cookie, writes a purchase event and conversion atomically, and leaves contributor selection to the evidence ledger. It does not verify payment or settle royalties.

`scripts/run_synthetic_scenarios.py` exercises the full local path from clean SQLite fixtures and preserves receipts in `examples/scenario-receipts/`. The direct case accrues synthetic royalty; ambiguous and no-click cases remain `unknown` with zero royalty.

`scripts/verify_synthetic_scenarios.py` independently reopens the SQLite files, recomputes reports, compares them with the JSON receipts, and writes `examples/scenario-receipts/verification.json` with artifact hashes.

With the local server running, `scripts/verify_local_http.py` independently compares `GET /v1/reports` to a reopened SQLite report, checks the dashboard at `/`, and proves the database hash is unchanged by readback.

`scripts/replay_http_scenarios.py` drives direct, ambiguous, and no-click cases through the actual local HTTP endpoints and preserves receipts in `examples/http-scenario-receipts/`.

To inspect the fixed scenario set locally:

```bash
PYTHONPATH=src:scripts python3 scripts/serve_synthetic_report.py --scenario-dir examples/scenario-receipts --port 8080
```

The dashboard selector only addresses the fixed server-side scenario names. It cannot select arbitrary files and has no mutation controls.

Check the running local process before opening the dashboard:

```bash
PYTHONPATH=src:scripts python3 scripts/check_local_server.py --base-url http://127.0.0.1:8080
```

Check SQLite recovery across a bounded local restart:

```bash
PYTHONPATH=src:scripts python3 scripts/check_restart_recovery.py --output-dir examples/recovery-receipts
```

Check local negative paths and logical ledger preservation:

```bash
PYTHONPATH=src:scripts python3 scripts/check_negative_paths.py --output-dir examples/negative-path-receipts
```

Check local SQLite backup and restore fidelity:

```bash
PYTHONPATH=src:scripts python3 scripts/check_backup_restore.py --output-dir examples/backup-recovery-receipts
```

Verify the local event hash chain:

```bash
PYTHONPATH=src:scripts python3 scripts/check_ledger_integrity.py \
  --sqlite examples/scenario-receipts/direct.sqlite
```
