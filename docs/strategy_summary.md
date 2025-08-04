# Strategy Summary API

`GET /strategies/summary` aggregates the latest metrics, risk statistics and weights
for every strategy.

Example response:

```json
{
  "strategies": [
    {
      "id": "pf1",
      "name": "Momentum",
      "weights": {"AAPL": 0.5, "MSFT": 0.5},
      "metrics": {"date": "2024-01-01", "ret": 0.02},
      "risk": {"date": "2024-01-01", "var95": -0.05, "vol30d": 0.12}
    }
  ]
}
```
