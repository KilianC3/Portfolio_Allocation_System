# Portfolio Allocation System (PAS)

PAS automates strategy allocation, execution and analytics in a single
service. Scrapers gather market data, analytics modules compute momentum and
fundamental signals and strategies rebalance portfolios through a FastAPI
interface. State lives in MariaDB with Redis providing a lightweight cache.

## Overview

The API exposes endpoints for analytics, generic database access and trade
execution. APScheduler handles recurring jobs while Prometheus metrics and a
dashboard endpoint offer observability. The system can be deployed with Docker
or orchestrated in Kubernetes and supports both paper and live trading through
Alpaca.

## Requirements

The project targets Python 3.10 or newer. Running the full stack requires
MariaDB 10+, Redis 6+ and an Alpaca API key. Docker Compose is the simplest way
to launch all services, though each component can run locally if the required
services are available.

## Quick Start

Clone the repository and populate `config.yaml` or a `.env` file with your
credentials and connection strings. From the project root, start the stack:

```bash
docker-compose up --build
```

The API listens on `http://192.168.0.59:8001` by default and provides a
dashboard at `/dashboard` and interactive docs at `/docs`.

## API Highlights

Authentication uses a bearer token supplied via the `Authorization` header.
Endpoints include a generic `/db/{table}` proxy, portfolio analytics such as
correlation and sector exposure, and execution helpers for submitting rebalance
orders. WebSocket feeds publish price ticks, fills and equity updates. Metrics
are available at `/metrics` and a simple health probe lives at `/health`.
Momentum and fundamental datasets are exposed through collection routes like
`/collect/volatility_momentum` and `/collect/fundamentals` with matching `GET`
endpoints to read the stored records. Risk analytics are surfaced under
`/risk/*` where overview, VaR/ES, drawdowns, volatility, beta, correlations,
rule management and alert streaming expose nightly computed metrics for each
strategy.

Cross-origin requests are allowed for `GET` endpoints, so a front-end can fetch
protected resources by appending `?token=` with the API key.

## Monitoring, Testing and Deployment

Prometheus scrapes runtime metrics and Grafana can be layered on top for
dashboards and alerting. Run `pytest -q` to execute the unit test suite. GitHub
Actions builds, lints and tests the project and publishes container images for
deployment to a staging or production environment.

## Contributing and License

Pull requests are welcome; please discuss major changes via an issue first.
The codebase is released under the MIT license.

