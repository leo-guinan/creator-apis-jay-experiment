# Local synthetic conversion contract

Status: implemented localhost-only reference slice.

## Endpoint

`POST /v1/conversions`

Request JSON:

```json
{
  "conversion_id": "conversion:demo-001",
  "amount_cents": 100000
}
```

The request must include either `session_id` in the JSON body or the `capi_session` cookie created by `GET /r/<route_id>`. The endpoint then atomically persists:

- a synthetic `purchase` event;
- a conversion record linked to that purchase event;
- the campaign and experiment scope from the local ledger.

`purchase_event_id` may be supplied for deterministic fixtures. Otherwise it is derived from the conversion ID.

Identical conversion replay is idempotent. Reusing a conversion ID with different data is rejected. Negative amounts, non-integer amounts, unknown fields, malformed bodies, and requests without a session fail with `400`.

## Attribution boundary

The endpoint records a conversion; it does not choose a contributor. The existing evidence ledger performs attribution afterward. One valid route click produces `direct`; multiple valid route clicks in the same session remain `unknown`; unknown attribution accrues no royalty.

All data is synthetic and local. This endpoint is not payment verification, settlement, a customer identity system, or proof of causation. It must not be exposed publicly under the current runtime decision.
