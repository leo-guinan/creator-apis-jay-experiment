from pathlib import Path

from creator_apis.sqlite_store import SQLiteLedgerStore
from build_synthetic_receipt import build_fixture


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "examples" / "synthetic-ledger.sqlite"
    if output.exists():
        output.unlink()
    SQLiteLedgerStore.create(output, build_fixture()[0])
    print(f"wrote {output}")


if __name__ == "__main__":
    main()