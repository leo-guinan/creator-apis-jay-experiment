# Source status policy contract

Source names are governed by an explicit local decision before import.

Statuses:

- `synthetic` — synthetic fixtures only;
- `approved_local_export` — explicitly approved local export;
- `rejected` — import is refused;
- `unknown` — import is refused until reviewed.

Register a decision:

    PYTHONPATH=src:scripts python3 scripts/register_source.py \
      --database examples/synthetic-ledger.sqlite \
      --source-name jay-local-export \
      --status approved_local_export \
      --operator leo \
      --reason "approved local export for bounded experiment"

Every decision records the previous status, new status, operator, reason, and timestamp. Batch import refuses unknown or rejected sources and rejects mixed-status batches atomically. `GET /v1/sources` exposes the registry and decision history read-only.

Synthetic sources are not production sources, and approval of a local export does not authorize public publication, payment settlement, or causal attribution.
