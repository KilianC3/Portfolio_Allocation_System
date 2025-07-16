# Agent Guide & Commit Conventions

This document helps Codex (or any future agent) produce clear, consistent commits for the portfolio allocation system.  All source files now live inside folders; only `README.md` remains at the project root.

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
  - Set `ALLOW_LIVE=True` in `service/config.yaml` to switch from paper to live trading.

---

## 3. Repository Layout

- `service/` – API, scheduler, startup helpers and configuration
- `execution/` – Alpaca gateway and execution helpers
- `analytics/` – metric collection and optimisation utilities
- `risk/` – exposure limits, correlation regimes and circuit breakers
- `strategies/` – individual trading strategies
- `infra/` – rate limiting and resilient scraping helpers
- `deploy/` – Dockerfile, requirements and other build assets
- `docs/` – extended documentation and AGENT guides

Recent updates added a central `schema.sql` file executed by
`database.init_db`, a `db_ping` health check used by startup validation and
expanded universe tables for the S&P 400, S&P 500 and Russell 2000.
The `ticker_scores` table stores composite metrics for each symbol.
Metrics store extensive performance stats including weekly volatility,
weekly Sortino ratio, ATR and RSI. Account equity is archived in separate
tables for paper and live trading.

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

## 5. Allocation Strategy Guidance

- Avoid combining too many overlapping signals as this inflates estimation error and hurts live performance.
- Heavy optimisation may show great backtests but can fail in production.
- The allocator now uses a tangency portfolio that maximises Sharpe ratio. Avoid overly complex combinations of signals unless they clearly improve results.
- Prefer simple momentum overlays or volatility scaling when signal quality varies.
- Clean weekly returns with a z-score filter and fall back to the last weight
  vector if computed volatility looks unreasonable.
