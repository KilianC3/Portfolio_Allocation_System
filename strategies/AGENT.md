# Folder Overview

Portfolio construction logic for each trading strategy.
Files here call out to `scrapers/` for data and rely on `analytics/` and
`risk/` modules to compute weights and limits. Each strategy exposes a
`build()` coroutine that updates a portfolio instance.
