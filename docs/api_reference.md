# API Reference

## `GET /db`

List all available database tables. The `system_logs` table is included so log
records can be inspected through the same interface as other datasets.

## `DELETE /db/system_logs`

Clear old log entries from the `system_logs` table. The optional `days`
parameter (default `30`) determines the age threshold of removed rows.

## `GET /db/{table}`

Return records from a database collection. Supports pagination, optional field
projection and sorting.

### Query Parameters

- `limit` – maximum number of records to return (default `50`).
- `page` – page number for pagination (default `1`).
- `format` – `json` (default) or `csv` response.
- `sort_by` – field name used to sort results.
- `order` – sort direction, `asc` or `desc` (default `asc`).
- `fields` – comma-separated list of fields to include in the response.

Example:

```
GET /db/returns?limit=10&sort_by=date&order=desc&fields=date,ret
```

## `POST /db/backup`

Export all MariaDB tables to JSON files under `database/backups` and commit the
snapshot to the repository. This is a lightweight data backup for historical
reference.

## `POST /db/restore`

Pull the latest backup snapshot from git and repopulate the MariaDB tables from
the JSON files.

## `GET /strategies`

Return the list of strategy classes available in the `strategies` package so the
front end can present every portfolio option even before metrics have been
computed.

