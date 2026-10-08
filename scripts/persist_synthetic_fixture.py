from pathlib import Path

from creator_apis.store import LedgerStore
from build_synthetic_receipt import build_fixture


def main() -> None:
    ledger, _ = build_fixture()
    output = Path(__file__).resolve().parents[1] / "examples" / "synthetic-ledger.json"
    LedgerStore.save(ledger, output)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
