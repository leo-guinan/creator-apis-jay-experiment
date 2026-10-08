# Creator APIs — Jay Evidence Experiment

This repository is a bounded, public working experiment for Creator APIs. It starts from the approved Jay + Leo conversation and tests whether a human contribution can be traced through derived content to a directly attributable value event.

## Current status

Implemented and verified locally:

`campaign/experiment → contributor → source → content block → artifact → placement(s) → route click → purchase → direct attribution → synthetic royalty accrual`

The implementation is a local Python reference slice. It does not publish to external platforms, process payments, settle royalties, or establish validated economics.

## Run the verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 scripts/build_synthetic_receipt.py
```

The generated receipt is `examples/synthetic-evidence-receipt.json`. It is explicitly marked `fixture_status: synthetic` and includes YouTube and X placement/route records under one campaign and experiment.

## Documentation

- `docs/project-start.md` — source boundary, work completed, and next slice.
- `docs/v0-evidence-ledger-contract.md` — record model and direct-attribution rules.
- `docs/jay-conversation-ledger.md` — source-derived observations, implications, and falsifiers.
- `docs/sources/creator-apis-initial-architecture.md` — supplied architecture brief.
- `docs/transcripts/` — approved timestamped transcript artifacts from the Jay recording.

## Privacy and provenance boundary

The raw recording remains at its original local path and is not copied into this repository. Leo confirmed that Jay approved recording and publication to the YouTube channel; the transcript is therefore included as a narrower public, source-linked working artifact. Source-derived observations remain labeled, and synthetic fixture output must not be read as a real payment, customer conversion, platform publication, or settled royalty.

## Implemented next slice

Campaign and experiment identifiers now propagate through records, events, conversions, and attribution results. Multiple placements/routes are supported, and ambiguous same-session route clicks remain `unknown` rather than being assigned to a channel by guesswork.

The next boundary is a query/reporting surface over this ledger; live platform adapters and payment settlement remain out of scope.
