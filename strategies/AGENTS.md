# Folder Overview

Portfolio construction logic for each trading strategy.
Files here call out to `scrapers/` for data and rely on `analytics/` and
`risk/` modules to compute weights and limits. Each strategy exposes a
`build()` coroutine that updates a portfolio instance.
Strategies now cover the Congressional-Trading Aggregate, DC insider scores,
government contracts, app reviews, Google Trends and politician sleeves for
Nancy Pelosi, Dan Meuser and Shelley Moore Capito. They are executed on a
schedule and validated by unit tests.
