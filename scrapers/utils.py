import logging
import re
from typing import Any, Dict, Iterable, Optional, Type

from bs4.element import Tag


def get_column_map(table: Tag, aliases: Dict[str, Iterable[str]]) -> Dict[str, int]:
    """Return a mapping of field name to column index using header aliases."""
    headers = [h.get_text(strip=True).lower() for h in table.find_all("th")]
    mapping: Dict[str, int] = {}
    for field, keys in aliases.items():
        for key in keys:
            for i, header in enumerate(headers):
                if key in header:
                    mapping[field] = i
                    break
            if field in mapping:
                break
    return mapping


def clean_ticker(ticker: str) -> Optional[str]:
    if not ticker:
        return None
    t = ticker.strip().upper()
    return t if t.isalpha() else None


_num_re = re.compile(r"[,$]")


def parse_numeric(value: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(_num_re.sub("", value))
    except ValueError:
        return None


def validate_row(
    row: Dict[str, str],
    *,
    ticker_field: str = "ticker",
    numeric_fields: Optional[Dict[str, Type]] = None,
    log: Optional[logging.Logger] = None,
) -> Optional[Dict[str, Any]]:
    ticker = clean_ticker(row.get(ticker_field, ""))
    if not ticker:
        if log:
            log.warning("invalid ticker %s", row.get(ticker_field))
        return None
    row[ticker_field] = ticker
    for field, typ in (numeric_fields or {}).items():
        val = parse_numeric(row.get(field, ""))
        if val is None:
            if log:
                log.warning("invalid numeric field %s=%s", field, row.get(field))
            return None
        row[field] = typ(val)
    return row
