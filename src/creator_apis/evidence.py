from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AttributionResult:
    conversion_id: str
    classification: str
    contributor_id: str | None
    trace: list[str]
    evidence_event_ids: list[str]
    fixture_status: str


@dataclass(frozen=True)
class RoyaltyAccrual:
    conversion_id: str
    contributor_id: str
    collected_amount_cents: int
    rate: float
    amount_cents: int
    fixture_status: str


class EvidenceLedger:
    """Small append-only evidence ledger for the synthetic v0 trace."""

    def __init__(self, fixture_status: str = "synthetic"):
        if not fixture_status:
            raise ValueError("fixture_status is required")
        self.fixture_status = fixture_status
        self.records: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.conversions: dict[str, dict[str, Any]] = {}

    def _put(self, record_type: str, record_id: str, **fields: Any) -> None:
        if record_id in self.records:
            raise ValueError(f"duplicate record id: {record_id}")
        self.records[record_id] = {
            "record_type": record_type,
            "record_id": record_id,
            "fixture_status": self.fixture_status,
            **fields,
        }

    def add_contributor(self, contributor_id: str, name: str) -> None:
        self._put("contributor", contributor_id, name=name)

    def add_source(self, source_id: str, contributor_id: str) -> None:
        self._require(contributor_id)
        self._put("source", source_id, contributor_id=contributor_id)

    def add_content_block(self, block_id: str, source_id: str) -> None:
        self._require(source_id)
        self._put("content_block", block_id, source_id=source_id)

    def add_artifact(self, artifact_id: str, block_ids: list[str]) -> None:
        if not block_ids:
            raise ValueError("artifact requires at least one content block")
        for block_id in block_ids:
            self._require(block_id)
        self._put("artifact", artifact_id, block_ids=list(block_ids))

    def add_placement(self, placement_id: str, artifact_id: str, channel: str) -> None:
        self._require(artifact_id)
        self._put("placement", placement_id, artifact_id=artifact_id, channel=channel)

    def add_route(self, route_id: str, placement_id: str, destination: str) -> None:
        self._require(placement_id)
        self._put("route", route_id, placement_id=placement_id, destination=destination)

    def record_event(
        self,
        event_id: str,
        event_type: str,
        *,
        session_id: str | None = None,
        route_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if any(event["event_id"] == event_id for event in self.events):
            raise ValueError(f"duplicate event id: {event_id}")
        if route_id is not None:
            self._require(route_id)
        self.events.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "session_id": session_id,
                "route_id": route_id,
                "metadata": dict(metadata or {}),
                "fixture_status": self.fixture_status,
            }
        )

    def record_conversion(
        self,
        conversion_id: str,
        *,
        session_id: str,
        amount_cents: int,
        purchase_event_id: str,
    ) -> None:
        if conversion_id in self.conversions:
            raise ValueError(f"duplicate conversion id: {conversion_id}")
        if amount_cents < 0:
            raise ValueError("amount_cents cannot be negative")
        self.conversions[conversion_id] = {
            "conversion_id": conversion_id,
            "session_id": session_id,
            "amount_cents": amount_cents,
            "purchase_event_id": purchase_event_id,
            "fixture_status": self.fixture_status,
        }

    def direct_attribution(self, conversion_id: str) -> AttributionResult:
        conversion = self._conversion(conversion_id)
        matching_clicks = [
            event
            for event in self.events
            if event["event_type"] == "route_click"
            and event["session_id"] == conversion["session_id"]
            and event["route_id"] is not None
        ]
        for click in matching_clicks:
            trace = self._trace_for_route(click["route_id"])
            if trace is not None:
                return AttributionResult(
                    conversion_id=conversion_id,
                    classification="direct",
                    contributor_id=trace[-1],
                    trace=trace,
                    evidence_event_ids=[click["event_id"], conversion["purchase_event_id"]],
                    fixture_status=self.fixture_status,
                )
        return AttributionResult(
            conversion_id=conversion_id,
            classification="unknown",
            contributor_id=None,
            trace=[],
            evidence_event_ids=[],
            fixture_status=self.fixture_status,
        )

    def accrue_royalty(self, conversion_id: str, *, rate: float) -> RoyaltyAccrual:
        if not 0 <= rate <= 1:
            raise ValueError("rate must be between 0 and 1")
        result = self.direct_attribution(conversion_id)
        if result.classification != "direct" or result.contributor_id is None:
            raise ValueError("conversion is not directly attributable")
        amount = self._conversion(conversion_id)["amount_cents"]
        return RoyaltyAccrual(
            conversion_id=conversion_id,
            contributor_id=result.contributor_id,
            collected_amount_cents=amount,
            rate=rate,
            amount_cents=round(amount * rate),
            fixture_status=self.fixture_status,
        )

    def export(self) -> dict[str, Any]:
        return {
            "fixture_status": self.fixture_status,
            "records": {key: dict(value) for key, value in self.records.items()},
            "events": [dict(event) for event in self.events],
            "conversions": {key: dict(value) for key, value in self.conversions.items()},
        }

    def _require(self, record_id: str) -> dict[str, Any]:
        try:
            return self.records[record_id]
        except KeyError as exc:
            raise ValueError(f"unknown record id: {record_id}") from exc

    def _conversion(self, conversion_id: str) -> dict[str, Any]:
        try:
            return self.conversions[conversion_id]
        except KeyError as exc:
            raise ValueError(f"unknown conversion id: {conversion_id}") from exc

    def _trace_for_route(self, route_id: str) -> list[str] | None:
        route = self.records.get(route_id)
        if route is None or route["record_type"] != "route":
            return None
        placement = self.records.get(route["placement_id"])
        if placement is None:
            return None
        artifact = self.records.get(placement["artifact_id"])
        if artifact is None or not artifact["block_ids"]:
            return None
        block = self.records.get(artifact["block_ids"][0])
        if block is None:
            return None
        source = self.records.get(block["source_id"])
        if source is None:
            return None
        contributor_id = source["contributor_id"]
        if contributor_id not in self.records:
            return None
        return [route_id, placement["record_id"], artifact["record_id"], block["record_id"], source["record_id"], contributor_id]
