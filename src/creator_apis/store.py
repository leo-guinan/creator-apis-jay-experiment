import json
from pathlib import Path

from .evidence import EvidenceLedger


class LedgerStore:
    """JSON persistence for a ledger export; no external database required."""

    @staticmethod
    def save(ledger: EvidenceLedger, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(ledger.export(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def load(path: str | Path) -> EvidenceLedger:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "fixture_status" not in payload:
            raise ValueError("invalid ledger export")
        ledger = EvidenceLedger(
            fixture_status=payload["fixture_status"],
            campaign_id=payload.get("campaign_id"),
            experiment_id=payload.get("experiment_id"),
        )
        ledger.records = payload.get("records", {})
        ledger.events = payload.get("events", [])
        ledger.conversions = payload.get("conversions", {})
        return ledger
