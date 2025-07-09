# Folder Overview

Unit tests cover scrapers, strategies, database utilities and analytics. Each
test fetches one record from mocked data sources so the pipelines run without
network access. Strategy tests exercise the Congressional-Trading Aggregate
along with the Pelosi, Meuser and Capito sleeves and all other models. The
`pytest -q` command is run before every commit.
