# Creator APIs project start

Status: local experiment workspace with the first synthetic evidence-ledger slice implemented and published.

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

## Next slice

Add campaign/experiment identifiers and multiple placements/routes while preserving the same append-only event and direct-attribution boundaries. Do not add live platform publishing, payment settlement, or automated royalty payment until those contracts and consent rules are separately approved.

## Non-goals for the first slice

- No automatic publishing to YouTube, X, LinkedIn, or email.
- No payment processor integration or real royalty settlement.
- No copying of the raw recording into the repository; the approved transcript is public and source-linked.
- No claim that attribution is causal merely because a route was clicked.
- No tokenization, auction, or patronage mechanism.
