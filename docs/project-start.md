# Creator APIs project start

Status: local-only runtime validation with the synthetic evidence ledger, read-only reporting, JSON/SQLite persistence, versioned APIs, local route tracking, and local dashboard implemented. The source repository is public; the runtime is not.

## Source inputs

- Architecture brief: `docs/sources/creator-apis-initial-architecture.md`
  - Original path: `/Users/leoguinan/Downloads/Creator APIs initial architecture.md`
  - Copied into this repository on 2026-10-07.
- Jay + Leo recording:
  - Original directory: `/Users/leoguinan/Untitled/2026-10-07 12.02.39 Jay + Leo/`
  - Audio source: `audio1600851425.m4a`
  - Video source: `video1600851425.mp4`
  - Recording duration: 3157.098667 seconds (52m 37s), stereo AAC, 48 kHz.
  - Transcript outputs are generated under `docs/transcripts/` and must be treated as source-derived working material pending listening/review.

Publication status: Leo confirmed that Jay approved recording and publication to the YouTube channel; the transcript is therefore approved for this public repository as a narrower, source-linked working artifact. The raw recording remains at its original local path and is not copied here.

## Initial working thesis

Build the smallest auditable loop that can answer: how much value was created by a human contribution, what evidence supports that claim, and what value is returned to that contributor?

The first bounded demonstration is Jay's contribution flowing through content blocks, artifacts, placements, first-party routes, observed events, a directly attributable purchase, and a royalty calculation. This is an experiment and architecture target, not evidence that the economics work.

## Repository boundary

This workspace is intentionally separate from the existing `/Users/leoguinan/Creator-APIs` repository, which contains unrelated modified and untracked architecture/deployment work. No existing implementation was copied into this experiment workspace.

Runtime decision: keep the ledger, SQLite database, event-ingestion API, and dashboard bound to localhost while mechanism reliability is established. See `docs/decisions/0001-local-runtime.md`.

## Completed first slice

1. Preserved and inspected the full Jay recording transcript.
2. Converted the architecture brief and conversation into a source-labeled decision ledger.
3. Froze the smallest v0 contract in `docs/v0-evidence-ledger-contract.md`.
4. Implemented a local `EvidenceLedger` in `src/creator_apis/evidence.py`.
5. Exercised the complete synthetic trace with a generated receipt at `examples/synthetic-evidence-receipt.json`.

Verification receipt:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` → 3 tests passed.
- Synthetic attribution classification: `direct`.
- Synthetic collected amount: `$1,000`.
- Synthetic royalty at 10%: `$100` (`10,000` cents).
- All exported records are explicitly marked `fixture_status: synthetic`.

## Completed second slice

Added campaign and experiment identifiers across records, events, conversions, and attribution results. Added independent YouTube and X placements/routes and an ambiguity guard: multiple valid route clicks in one session remain `unknown` rather than being assigned retroactively.

Verification:

- `PYTHONPATH=src python3 -m unittest tests/test_evidence.py -v` → 5 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` → 5 tests passed.
- `PYTHONPATH=src python3 scripts/build_synthetic_receipt.py` → direct / 10,000 cents / synthetic.
- Remote receipt contains both `placement:youtube-jay-clip-v1` and `placement:x-jay-clip-v1` under `experiment:ai-roi-am`.

## Completed third slice

Added JSON persistence with report-equivalent round trips and a versioned read-only HTTP endpoint: `GET /v1/reports`.

Verification:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` → 10 tests passed.
- JSON store round trip preserved the complete scoped report.
- Live local HTTP readback returned `api_version: v1`, two placements, and 10,000 synthetic royalty cents.
- `examples/synthetic-ledger.json` is the persisted synthetic fixture.

## Completed fourth slice

Added SQLite-backed append-only event ingestion at `POST /v1/events`. Identical event replays are idempotent, conflicting IDs are rejected, unknown routes are rejected, and report reads reload the durable store.

Verification:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` → 13 tests passed.
- Event survived a SQLite store-object reload.
- HTTP `POST /v1/events` returned `201` on first write and `200`/`created: false` on replay.
- HTTP `GET /v1/reports` reflected the durable event.
- Unknown route ingestion returned HTTP 400.

## Completed fifth slice

Added `app/index.html`, a read-only same-origin dashboard served at `/`. It displays fixture status, scope, channel coverage, placements/routes, attribution, and direct royalty totals from `GET /v1/reports`.

Verification:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` → 15 tests passed.
- Dashboard source contract checks passed.
- Local HTTP readback returned `Content-Type: text/html; charset=utf-8` and 5,289 bytes of dashboard HTML.
- Dashboard API readback returned `api_version: v1` and 2 placements.

## Completed sixth slice

Added local `GET /r/<route_id>` tracking. Valid routes append timestamped route-click events to SQLite, establish/reuse a localhost session cookie, and return a `302` redirect. Unknown routes fail with `404` and do not write an event.

Verification:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` → 17 tests passed.
- Two sequential redirects with the same cookie produced two append-only events with the same session ID.
- Route destination readback returned the configured calibration URL.
- Unknown route readback returned HTTP 404.

## Next slice

Add a local synthetic conversion-recording path so the route click can flow into a conversion without hand-authoring purchase JSON. Do not add live platform publishing, payment settlement, or automated royalty payment until those contracts and consent rules are separately approved.

## Non-goals for the first slice

- No automatic publishing to YouTube, X, LinkedIn, or email.
- No payment processor integration or real royalty settlement.
- No copying of the raw recording into the repository; the approved transcript is public and source-linked.
- No claim that attribution is causal merely because a route was clicked.
- No tokenization, auction, or patronage mechanism.
