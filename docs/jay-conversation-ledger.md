# Jay conversation decision ledger

Status: source-derived working ledger. Quotes and interpretations require review against the recording before publication. Timestamps refer to `docs/transcripts/audio1600851425.json` generated from the local recording with Whisper `base`.

## Observed in the recording

| Time | Observation | Implication for Creator APIs | Confidence |
|---|---|---|---|
| 00:03–00:30 | Leo describes Building Public University as a professor/student system whose objective is reducing student payback period and increasing leverage over time. | Keep learning outcomes and payback measurable; do not reduce the product to model access. | Transcript-derived; review audio before quoting. |
| 03:04–03:08 | “Magic” is defined as “work not done”; the business system should remove work while outcomes stay stable or improve. | Candidate north-star metric: outcome value relative to Leo/customer time required. | Transcript-derived; review audio before quoting. |
| 08:32–09:18 | The conversation distinguishes a $1,000 calibration phase from a proposed $250/month continuation; the recurring model was explicitly not fully validated. | Treat prices as experiment parameters, not established economics. | Transcript-derived; explicit uncertainty. |
| 12:42–12:46 | Jay says he likes “movies, not snapshots,” in the context of showing work over time. | Build a longitudinal evidence trail rather than isolated claims. | Transcript-derived; review audio before quoting. |
| 16:31–16:35 | A near-term target of at least five calls per week is discussed. | Track attention → qualified call transitions separately from revenue. | Transcript-derived; review audio before quoting. |
| 16:40–17:05 | Jay asks for a narrower audience and clearer promise; Leo describes creators/builders with weak leverage or worsening results in the AI era. | Audience and promise need a bounded experiment, not a broad “AI can do everything” category. | Transcript-derived; interpretation to validate. |
| 27:49–29:13 | Leo describes Creator APIs as an open-source project intended to layer human-created data on AI workflows and reward the humans contributing to queries; Enchanted Notebook is described as a first product direction. | Preserve the canonical model: humans in front, AI behind; provenance before economic claims. | Transcript-derived; review audio before quoting. |
| 52:00–52:14 | Leo states that a first $10K month would be a trust milestone and says he will update Jay. | This is a prospective milestone, not achieved proof. Store as a dated commitment/measurement target. | Direct transcript observation. |

## Architecture commitments carried from the supplied brief

1. Store observations before attribution interpretations.
2. Keep artifacts independent of placements and channels.
3. Give internal entities stable IDs before external platform IDs.
4. Preserve provenance from human source → content block → artifact → placement → route → event → conversion.
5. Start with direct attribution only; keep assisted and unknown outcomes visible.
6. Treat a 10% Jay royalty on directly attributable collected revenue as a proposed initial rule requiring explicit agreement and settlement verification.
7. Prefer manual publishing and build measurement first.
8. Keep the raw Jay recording private; the transcript is approved for public repository use under Leo's confirmation of Jay's recording/publication consent.

## Falsifiers / stop conditions

- A route click cannot be joined to a conversion: direct attribution remains unknown.
- A content artifact cannot be traced to a permitted source: it cannot enter the royalty calculation.
- A conversion is observed but collected revenue is not verified: no royalty accrual is claimed.
- The system reduces Leo time but degrades customer outcomes: “work not done” is not demonstrated.
- The offer attracts attention but not qualified calls or purchases: the audience/promise hypothesis is rejected or revised.
- A transcript-derived statement differs materially from the recording: preserve the discrepancy and do not publish the quote.

## Implemented executable slice

The local v0 evidence ledger now tests the full trace with synthetic fixtures:

`contributor → source → content block → artifact → placement → route click → purchase → direct attribution → royalty accrual`

The implementation is in `src/creator_apis/evidence.py`; its contract is in `docs/v0-evidence-ledger-contract.md`; and the reproducible receipt is `examples/synthetic-evidence-receipt.json`.

Observed verification:

- `direct` attribution reaches `contributor:jay` through the route, placement, artifact, content block, and source.
- Synthetic `$1,000` collected revenue produces a synthetic `$100` royalty accrual at 10%.
- A session mismatch remains `unknown` and cannot accrue a royalty.
- Two events with distinct IDs remain present in append-only order.
- Campaign `campaign:jay-14day-001` and experiment `experiment:ai-roi-am` propagate through the exported records.
- YouTube and X placements/routes coexist under the same artifact and experiment.
- Multiple valid route clicks in one session return `unknown` with `ambiguous_route_clicks` rather than guessed attribution.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passes 10 tests.

The read-only reporting surface is implemented in `src/creator_apis/reporting.py`; its contract is in `docs/reporting-contract.md`; and the generated report is `examples/synthetic-report.json`. It reports scoped counts, channel coverage, event types, attribution results, evidence traces, and direct royalty totals without mutating the ledger.

JSON persistence is implemented in `src/creator_apis/store.py`; SQLite event persistence is in `src/creator_apis/sqlite_store.py`; the versioned local HTTP boundary is in `src/creator_apis/api.py`; and the persisted fixture is `examples/synthetic-ledger.json`. `POST /v1/events` is idempotent for identical replays, while `GET /v1/reports` returns an explicit `v1` envelope from the durable store.

The local browser dashboard is implemented in `app/index.html` and documented in `docs/dashboard-contract.md`. It is read-only and renders the report without changing attribution semantics.

The local tracked-route endpoint is implemented in `src/creator_apis/api.py` and documented in `docs/routing-contract.md`. It records timestamped clicks and preserves a session join before redirecting; a click remains an observation, not a conversion.

The local synthetic conversion endpoint is implemented in `src/creator_apis/api.py` and `src/creator_apis/sqlite_store.py`, documented in `docs/conversion-contract.md`. It writes a purchase event and conversion from the route session, while leaving contributor selection and royalty eligibility to the evidence ledger.

The local scenario runner is implemented in `scripts/run_synthetic_scenarios.py` and documented in `docs/scenario-runner-contract.md`. It preserves direct, ambiguous, and no-click receipts so the evidence rules can be inspected without relying on a hand-authored single happy path.

The independent verifier is implemented in `scripts/verify_synthetic_scenarios.py` and documented in `docs/scenario-verification-contract.md`. It recomputes reports from reopened SQLite state and preserves artifact hashes; it does not treat a self-generated receipt as sufficient evidence of persistence.

The independent HTTP verifier is implemented in `scripts/verify_local_http.py` and documented in `docs/http-readback-contract.md`. It compares the running localhost API to the reopened SQLite report, checks the dashboard, and confirms the read path leaves the database unchanged.

The HTTP scenario replay harness is implemented in `scripts/replay_http_scenarios.py` and documented in `docs/http-scenario-replay-contract.md`. It proves the direct, ambiguous, and no-click paths through the actual route and conversion endpoints rather than writing those events directly to SQLite.

The local operator selector is implemented in `src/creator_apis/api.py`, `scripts/serve_synthetic_report.py`, and `app/index.html`, documented in `docs/operator-scenario-selector.md`. It exposes only fixed synthetic scenarios and remains read-only.

The health/readiness boundary is implemented in `src/creator_apis/api.py` and `scripts/check_local_server.py`, documented in `docs/health-readiness-contract.md`. It makes stale or incompatible local server processes observable before the operator trusts the dashboard.

The fixture remains synthetic. It does not imply a real Jay payment, real customer, real platform publication, or validated economics. The next slice is an operator workflow decision, not public exposure.
