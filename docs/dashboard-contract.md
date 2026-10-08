# Local dashboard contract

Status: implemented local reference dashboard. Read-only and synthetic-fixture oriented.

## Surface

The server serves `app/index.html` at `/`. The dashboard fetches `GET /v1/reports` and renders:

- API version and fixture status.
- Campaign and experiment scope.
- Event, placement, conversion, and direct-royalty cards.
- Placement/channel coverage and route IDs.
- Attribution classification, contributor, and provenance trace.

The dashboard does not write events, calculate a second attribution model, or hide unknown/ambiguous results.

## Boundary

This is a same-origin local client of the existing report endpoint. The current server has no authentication, TLS, rate limiting, CSP, or multi-tenant isolation. It must not be deployed publicly without a separate security and deployment design.
