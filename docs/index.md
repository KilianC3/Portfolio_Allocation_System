# Portfolio Allocation System

This documentation complements the README with details on the scraped data and how it is stored. Browse the sections below for deeper explanations and API usage.

- [Data Store Format](./data_format.md)
- [API Reference](./api_reference.md)

Refer to the README for setup and usage instructions. The MariaDB layer now
supports a configurable connection pool size via the `DB_POOL_SIZE`
environment variable. Indexes on `metrics(portfolio_id)` and
`ticker_scores(index_name)` speed up common queries.
