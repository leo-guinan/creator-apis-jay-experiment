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
8. Keep the Jay recording private; public reuse requires consent and review.

## Falsifiers / stop conditions

- A route click cannot be joined to a conversion: direct attribution remains unknown.
- A content artifact cannot be traced to a permitted source: it cannot enter the royalty calculation.
- A conversion is observed but collected revenue is not verified: no royalty accrual is claimed.
- The system reduces Leo time but degrades customer outcomes: “work not done” is not demonstrated.
- The offer attracts attention but not qualified calls or purchases: the audience/promise hypothesis is rejected or revised.
- A transcript-derived statement differs materially from the recording: preserve the discrepancy and do not publish the quote.

## Next executable slice

Create a local-only v0 evidence ledger and test the full trace with synthetic fixtures:

`contributor → source → content block → artifact → placement → route click → purchase → direct attribution → royalty accrual`

The fixture must label synthetic data as synthetic. It must not imply a real Jay payment, real customer, real platform publication, or validated economics.
