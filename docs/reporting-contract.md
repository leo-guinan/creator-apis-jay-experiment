# Read-only ledger reporting contract

Status: implemented local reference slice. Synthetic fixture only.

## Surface

`LedgerReport(ledger).summary(...)` returns a JSON-serializable report without mutating the ledger.

Optional scope filters:

- `campaign_id`
- `experiment_id`
- `royalty_rate` (set to `None` to report attribution without calculating royalty)

When omitted, campaign and experiment scope defaults to the ledger's own IDs.

## Report shape

- `fixture_status`: synthetic/other ledger status.
- `scope`: effective campaign and experiment IDs.
- `counts`: contributors, sources, content blocks, artifacts, placements, routes, events, and conversions in scope.
- `placements`: channel, artifact, and route IDs for each placement.
- `placements_by_channel`: channel counts.
- `events_by_type`: append-only event counts.
- `attributions`: one direct/unknown result per in-scope conversion, including trace, evidence event IDs, and ambiguity reason.
- `royalty`: explicit rate, directly attributable collected amount, and accrued amount.

## Boundaries

The report is descriptive, not causal beyond the ledger's direct join rule. It excludes out-of-scope records, preserves unknown and ambiguous attribution, and never creates a payout or sends an external message. It does not import platform metrics, query a payment provider, or claim validated economics.
