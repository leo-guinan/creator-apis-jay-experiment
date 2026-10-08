import json
from pathlib import Path

from creator_apis.reporting import LedgerReport
from build_synthetic_receipt import build_fixture


def main() -> None:
    ledger, _ = build_fixture()
    report = LedgerReport(ledger).summary(royalty_rate=0.10)
    output = Path(__file__).resolve().parents[1] / "examples" / "synthetic-report.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    print("placements_by_channel=", report["placements_by_channel"])
    print("attributions=", len(report["attributions"]))
    print("accrued_amount_cents=", report["royalty"]["accrued_amount_cents"])


if __name__ == "__main__":
    main()
