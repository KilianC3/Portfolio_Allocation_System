# API Reference

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
