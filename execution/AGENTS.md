# Folder Overview

Broker connectivity helpers.
- `gateway.py` wraps the Alpaca REST API for order submission and account
  queries.

Strategies construct trades through these utilities after computing weights.
The gateway checks for paper vs live trading endpoints and exposes a
`allow_live` flag so unit tests avoid real orders.
