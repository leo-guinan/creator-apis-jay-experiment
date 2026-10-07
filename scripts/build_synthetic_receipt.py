import json
from pathlib import Path

from creator_apis.evidence import EvidenceLedger


def build_fixture() -> tuple[EvidenceLedger, dict]:
    ledger = EvidenceLedger(fixture_status="synthetic")
    ledger.add_contributor("contributor:jay", "Jay")
    ledger.add_source("source:jay-interview", "contributor:jay")
    ledger.add_content_block("block:work-not-done", "source:jay-interview")
    ledger.add_artifact("artifact:jay-clip-v1", ["block:work-not-done"])
    ledger.add_placement("placement:youtube-jay-clip-v1", "artifact:jay-clip-v1", "youtube")
    ledger.add_route(
        "route:jay-youtube-001",
        "placement:youtube-jay-clip-v1",
        "https://example.test/calibration",
    )
    ledger.record_event(
        "event:click-1",
        "route_click",
        session_id="session:1",
        route_id="route:jay-youtube-001",
    )
    ledger.record_event(
        "event:purchase-1",
        "purchase_1000",
        session_id="session:1",
        metadata={"amount_cents": 100_000},
    )
    ledger.record_conversion(
        "conversion:1",
        session_id="session:1",
        amount_cents=100_000,
        purchase_event_id="event:purchase-1",
    )
    attribution = ledger.direct_attribution("conversion:1")
    accrual = ledger.accrue_royalty("conversion:1", rate=0.10)
    receipt = ledger.export()
    receipt["attribution"] = {
        "conversion_id": attribution.conversion_id,
        "classification": attribution.classification,
        "contributor_id": attribution.contributor_id,
        "trace": attribution.trace,
        "evidence_event_ids": attribution.evidence_event_ids,
        "fixture_status": attribution.fixture_status,
    }
    receipt["royalty_accrual"] = {
        "conversion_id": accrual.conversion_id,
        "contributor_id": accrual.contributor_id,
        "collected_amount_cents": accrual.collected_amount_cents,
        "rate": accrual.rate,
        "amount_cents": accrual.amount_cents,
        "fixture_status": accrual.fixture_status,
    }
    return ledger, receipt


def main() -> None:
    _, receipt = build_fixture()
    output = Path(__file__).resolve().parents[1] / "examples" / "synthetic-evidence-receipt.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    print("classification=", receipt["attribution"]["classification"])
    print("royalty_amount_cents=", receipt["royalty_accrual"]["amount_cents"])
    print("fixture_status=", receipt["fixture_status"])


if __name__ == "__main__":
    main()
