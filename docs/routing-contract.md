# Local tracked-route contract

Status: implemented localhost-only reference slice.

## Endpoint

`GET /r/<route_id>`

The endpoint:

1. validates the route against the durable SQLite ledger;
2. creates or reuses the `capi_session` localhost cookie;
3. appends a `route_click` event with a UTC `observed_at` timestamp;
4. returns `302` to the route's configured destination.

Each request creates a distinct append-only event. Reusing the session cookie preserves the session join needed for later synthetic conversion tests.

## Errors

- Unknown route: `404` JSON error; no redirect and no event.
- Empty route ID: `400` JSON error.
- Non-durable server configuration: ingestion fails closed rather than redirecting.

## Boundary

This is local mechanism validation. The cookie is not an identity system, the route click is not proof of causation, and the redirect does not imply a conversion. The server remains localhost-only under `docs/decisions/0001-local-runtime.md`.
