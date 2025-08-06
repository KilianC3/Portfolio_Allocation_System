"""Convenience wrappers aggregating weekly momentum scrapers."""

from .volatility_momentum import fetch_volatility_momentum_summary
from .leveraged_sector_momentum import fetch_leveraged_sector_summary
from .sector_momentum import fetch_sector_momentum_summary
from .smallcap_momentum import fetch_smallcap_momentum_summary
from .upgrade_momentum import fetch_upgrade_momentum_summary

__all__ = [
    "fetch_volatility_momentum_summary",
    "fetch_leveraged_sector_summary",
    "fetch_sector_momentum_summary",
    "fetch_smallcap_momentum_summary",
    "fetch_upgrade_momentum_summary",
]
