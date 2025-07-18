# Folder Overview

Core data classes representing portfolios and assets.
- `portfolio.py` – base Portfolio class and helpers.
- `equity.py` – EquityPortfolio implementation.
- `__init__.py` – exports convenience constructors.

These classes are used by strategies and analytics across the project.
Recent commits introduced chunked return fetching and portfolio tracking for
large universes which rely heavily on these base dataclasses.

- **Reminder:** triple-check modifications and run tests to prevent regressions.
