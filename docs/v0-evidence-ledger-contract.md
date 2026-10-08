# v0 evidence ledger contract

Status: implemented local reference slice with campaign/experiment identity and multiple placement routes. Synthetic fixture only; no live customer, platform, payment, or royalty data.

## Purpose

Prove the narrowest auditable trace:

`contributor → source → content block → artifact → placement → route click → purchase → direct attribution → royalty accrual`

This is a protocol-shaped local fixture, not a production payment or attribution system.

## Records

- `Contributor`: human whose permitted contribution may receive value.
- `Source`: source record linked to a contributor.
- `ContentBlock`: reusable content derived from a source.
- `Artifact`: complete content item assembled from content blocks.
- `Placement`: artifact published on a named channel; publication is represented locally only.
- `Route`: first-party tracking link connected to a placement and destination.
- `Event`: append-only observation. Events are never rewritten when attribution changes.
- `Conversion`: verified amount and purchase event reference.
- `AttributionResult`: direct, assisted, or unknown classification with an evidence trace.
- `RoyaltyAccrual`: calculated amount derived from collected revenue and an explicit royalty rate.

Every record, event, and conversion carries `campaign_id` and `experiment_id`. Placements and routes may inherit the ledger scope or provide an explicit scope, so one artifact can be compared across channels without making external IDs the core identity.

## Direct attribution rule

A conversion is `direct` only when:

1. A `route_click` event exists for the conversion's session.
2. The click references a registered route.
3. The route resolves to a placement, artifact, content block, source, and contributor.
4. A purchase conversion references the same session.
5. Collected revenue is explicitly present and non-negative.

A missing or mismatched join returns `unknown`; the ledger never fabricates credit.

If more than one valid route click exists for the conversion's session, the result is `unknown` with reason `ambiguous_route_clicks`. The ledger does not pick a winning channel after the fact.

## Synthetic-data boundary

Every ledger export includes `fixture_status: synthetic`. Every record carries the same status. Synthetic records cannot be interpreted as evidence of a real Jay payment, real platform publication, validated conversion rate, or settled royalty.

## Royalty rule

The fixture accepts an explicit rate. The demonstration uses `0.10`, producing a synthetic `$100` accrual from synthetic `$1,000` collected revenue. This calculation is not a payment instruction or settlement receipt.
