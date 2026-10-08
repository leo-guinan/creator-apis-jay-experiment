# Durable event ingestion contract

Status: implemented local reference slice. SQLite-backed and localhost-only by decision.

## Endpoint

`POST /v1/events`

Request body:

```json
{
  "event_id": "event:click-001",
  "event_type": "route_click",
  "session_id": "session:001",
  "route_id": "route:jay-youtube-001",
  "metadata": {}
}
```

`event_id` and `event_type` are required. `route_id`, `session_id`, `metadata`, `campaign_id`, and `experiment_id` are optional. A route reference must already exist in the durable ledger. Campaign and experiment IDs inherit from the route or ledger scope unless explicitly supplied.

Response:

- `201` with `created: true` for a new event.
- `200` with `created: false` when the identical `event_id` and payload are replayed.
- `400` for malformed JSON, unknown fields, invalid references, or conflicting reuse of an event ID.

## Persistence

`SQLiteLedgerStore` stores metadata, records, conversions, and append-only events in SQLite with WAL journaling. `ReportingAPI` reloads the ledger from the store for every report request, so a process/store-object restart does not erase appended events.

## Boundaries

Ingestion records observations only. It does not rewrite prior events, perform attribution at write time, send external messages, or settle royalties. The local reference server and dashboard have no authentication, TLS, rate limiting, CSP, or multi-tenant isolation and must not be exposed publicly. The dashboard boundary is documented in `docs/dashboard-contract.md`.
