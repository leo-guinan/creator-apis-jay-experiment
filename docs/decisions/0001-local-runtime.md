# ADR 0001: Keep the runtime local during mechanism validation

Status: accepted
Date: 2026-10-08

## Decision

Keep the Creator APIs evidence ledger, SQLite persistence, event-ingestion API, and browser dashboard local-only while the mechanisms are being validated.

The GitHub repository may remain public as a source and documentation surface. Public source availability is not public runtime availability.

## Why

The current system is useful as a bounded experiment, but it does not yet provide:

- authentication or authorization;
- TLS or deployment hardening;
- rate limiting and abuse controls;
- multi-tenant isolation;
- durable backup/restore policy;
- operational monitoring and recovery;
- production-grade consent and correction workflows.

Opening the runtime before those boundaries exist would turn a mechanism test into an avoidable operational liability. The market has enough unattended localhost servers posing as infrastructure.

## Local operating contract

- Bind the reference server to `127.0.0.1`.
- Use synthetic fixtures until real-source consent, correction, and retention rules are explicit.
- Keep SQLite persistence on the local machine; do not upload the database.
- Verify event append, replay idempotence, restart recovery, report readback, and dashboard rendering locally.
- Treat all royalty values as synthetic calculations until collection and settlement are independently verified.
- Do not add public deployment, public ingestion, or public dashboard access as an implicit consequence of repository publication.

## Promotion gate

A future public-viewing decision requires a separate written approval after these artifacts exist:

1. authentication and authorization contract;
2. privacy, consent, correction, and deletion policy;
3. backup/restore and migration procedure;
4. rate limiting and abuse controls;
5. deployment health checks and independent readback;
6. public/private data classification test;
7. explicit decision about whether ingestion is private, authenticated, or disabled.

Until then, “works” means the local test suite and local HTTP readback pass. It does not mean the service is public-ready.
