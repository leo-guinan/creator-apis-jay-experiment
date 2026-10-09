# Import manifest contract

Every event-batch attempt is now recorded in the local SQLite `import_batches` table. The manifest is append-only and survives receipt-directory loss. Imported source names are also recorded in the `sources` registry with status, first/last seen timestamps, and batch count.

Each manifest records:

- batch ID and source name;
- input hash;
- applied, duplicate, and rejected counts;
- integrity roots before and after;
- report digests before and after;
- timestamp and rejection errors.

`GET /v1/imports` exposes the manifests read-only. `GET /v1/sources` exposes the source registry. Replaying an identical batch does not create a second manifest. Reusing a batch ID with a different input hash is rejected.

Events imported from a batch carry the batch ID, so an imported event can be traced back to its durable manifest and source identity.
