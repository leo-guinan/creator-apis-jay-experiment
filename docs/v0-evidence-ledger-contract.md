# v0 evidence ledger contract

Status: implemented local reference slice. Synthetic fixture only; no live customer, platform, payment, or royalty data.

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

## Direct attribution rule

A conversion is `direct` only when:

1. A `route_click` event exists for the conversion's session.
2. The click references a registered route.
3. The route resolves to a placement, artifact, content block, source, and contributor.
4. A purchase conversion references the same session.
5. Collected revenue is explicitly present and non-negative.

A missing or mismatched join returns `unknown`; the ledger never fabricates credit.

## Synthetic-data boundary

Every ledger export includes `fixture_status: synthetic`. Every record carries the same status. Synthetic records cannot be interpreted as evidence of a real Jay payment, real platform publication, validated conversion rate, or settled royalty.

## Royalty rule

The fixture accepts an explicit rate. The demonstration uses `0.10`, producing a synthetic `$100` accrual from synthetic `$1,000` collected revenue. This calculation is not a payment instruction or settlement receipt.
