# Portfolio Allocation System

This project provides a set of utilities for allocating and rebalancing
quantitative trading portfolios.  A small FastAPI service is included in
`api.py` for simple HTTP access.

## API authentication

All endpoints expect an API key to be passed using the `x-api-key` HTTP
header.  The key value is read from the `API_KEY` environment variable at
startup.  If the variable is unset, requests do not require a key.

Example request:

```bash
curl -H "x-api-key: <your key>" http://localhost:8000/ping
```
