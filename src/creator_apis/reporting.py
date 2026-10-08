from collections import Counter
from typing import Any


class LedgerReport:
    """Read-only summaries over an EvidenceLedger."""

    def __init__(self, ledger):
        self.ledger = ledger

    def summary(
        self,
        *,
        campaign_id: str | None = None,
        experiment_id: str | None = None,
        royalty_rate: float | None = 0.10,
    ) -> dict[str, Any]:
        campaign_id = self.ledger.campaign_id if campaign_id is None else campaign_id
        experiment_id = self.ledger.experiment_id if experiment_id is None else experiment_id

        def in_scope(item: dict[str, Any]) -> bool:
            return (
                (campaign_id is None or item.get("campaign_id") == campaign_id)
                and (experiment_id is None or item.get("experiment_id") == experiment_id)
            )

        records = [record for record in self.ledger.records.values() if in_scope(record)]
        by_type = Counter(record["record_type"] for record in records)
        placements = [record for record in records if record["record_type"] == "placement"]
        routes = [record for record in records if record["record_type"] == "route"]
        events = [event for event in self.ledger.events if in_scope(event)]
        conversions = [
            conversion
            for conversion in self.ledger.conversions.values()
            if in_scope(conversion)
        ]

        placement_summaries = []
        for placement in placements:
            placement_routes = [
                route["record_id"]
                for route in routes
                if route["placement_id"] == placement["record_id"]
            ]
            placement_summaries.append(
                {
                    "placement_id": placement["record_id"],
                    "artifact_id": placement["artifact_id"],
                    "channel": placement["channel"],
                    "route_ids": placement_routes,
                }
            )

        attributions = []
        direct_collected = 0
        accrued = 0
        for conversion in conversions:
            result = self.ledger.direct_attribution(conversion["conversion_id"])
            attributions.append(
                {
                    "conversion_id": result.conversion_id,
                    "classification": result.classification,
                    "contributor_id": result.contributor_id,
                    "trace": result.trace,
                    "evidence_event_ids": result.evidence_event_ids,
                    "reason": result.reason,
                    "campaign_id": result.campaign_id,
                    "experiment_id": result.experiment_id,
                }
            )
            if result.classification == "direct" and royalty_rate is not None:
                accrual = self.ledger.accrue_royalty(
                    conversion["conversion_id"], rate=royalty_rate
                )
                direct_collected += accrual.collected_amount_cents
                accrued += accrual.amount_cents

        royalty = {
            "rate": royalty_rate,
            "direct_collected_amount_cents": direct_collected,
            "accrued_amount_cents": accrued,
        }
        return {
            "fixture_status": self.ledger.fixture_status,
            "scope": {
                "campaign_id": campaign_id,
                "experiment_id": experiment_id,
            },
            "counts": {
                "records": len(records),
                "contributors": by_type["contributor"],
                "sources": by_type["source"],
                "content_blocks": by_type["content_block"],
                "artifacts": by_type["artifact"],
                "placements": by_type["placement"],
                "routes": by_type["route"],
                "events": len(events),
                "conversions": len(conversions),
            },
            "placements": placement_summaries,
            "placements_by_channel": dict(
                sorted(Counter(item["channel"] for item in placements).items())
            ),
            "events_by_type": dict(sorted(Counter(event["event_type"] for event in events).items())),
            "attributions": attributions,
            "royalty": royalty,
        }
