# Agent Guide & Commit Conventions

This document helps Codex (or any future agent) produce clear, consistent commits for the portfolio allocation system.

---

## 1. Agent Overview

- **Purpose**: Automate feature development, bug fixes and documentation.
- **Scope**: Data scraping, universe management, risk models, scheduling and reporting.
- **Audience**: Developers and AI agents extending or maintaining the codebase.

---

## 2. Design Goals

1. **Modularity**
   - Keep scrapers, strategies, risk tools and analytics in separate modules.
   - Document interfaces so implementations can be swapped easily.
2. **Performance & Scalability**
   - Cache network calls and batch requests when possible.
   - Parallelise downloads where safe.
3. **Robustness**
   - Handle missing data and timeouts gracefully.
   - Use adaptive thresholds to avoid empty outputs.
4. **Extensibility**
   - Models and data sources should be pluggable.
   - Rolling windows (daily, weekly, monthly) must be configurable.
5. **Observability**
   - Provide structured logging and progress indicators.
   - Maintain unit tests for critical logic.
6. **Safety**
   - Detect paper vs live Alpaca endpoints and require `allow_live=True` for real trading.
   - Use the `AUTO_START_SCHED` flag so deployments can delay trading until explicitly enabled.

---

## 3. Repository Layout

- `api.py` – REST interface for the front end.
- `scheduler.py` – manages periodic strategy execution.
- `execution/` – Alpaca gateway and execution helpers.
- `analytics/` – metric collection and optimisation utilities.
- `risk/` – exposure limits, correlation regimes and circuit breakers.
- `strategies/` – individual trading strategies.
- `infra/` – rate limiting and resilient scraping helpers.

Recent updates added a central `schema.sql` file executed by
`database.init_db`, a `db_ping` health check used by startup validation and a
`universe` table storing S&P and Russell constituents.  Metrics now track 7‑day,
30‑day and 1‑year returns for every portfolio.

---

## 4. Commit Message Guidelines

Every commit should follow this template:

```
<summary line>

- bullet describing first change
- bullet describing next change

Testing:
- `pytest -q`
```

Additional rules:
- Format all Python with **black** before committing.
- Run `pytest -q` and include tests for new features when possible.
- Update the README or docs whenever behaviour or configuration changes.
- Keep commits focused and messages concise.
- If tests fail due to missing services (e.g. MongoDB) note the failure and
  reason in the PR summary.
