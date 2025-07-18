from typing import Dict, Optional
from bs4 import BeautifulSoup, Tag
import requests

from database import init_db
from service.logger import get_logger


def fetch_fundamentals(symbol: str) -> Dict[str, Optional[float]]:
    """Fetch key fundamental metrics from Finviz."""
    log = get_logger(__name__)
    log.info(f"fetch_fundamentals start symbol={symbol}")
    init_db()
    url = f"https://finviz.com/quote.ashx?t={symbol}&p=d&ty=ea"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    vals: Dict[str, float] = {}
    table = soup.find("table", class_="snapshot-table2")
    if isinstance(table, Tag):
        cells = [c.get_text(strip=True) for c in table.find_all("td")]
        for i in range(0, len(cells) - 1, 2):
            key = cells[i]
            val = cells[i + 1].replace("%", "").replace(",", "")
            try:
                vals[key] = float(val)
            except ValueError:
                continue
    log.info("fetch_fundamentals complete")
    return {
        "piotroski": vals.get("Piotroski F-Score"),
        "altman": vals.get("Altman Z-Score"),
        "roic": vals.get("ROIC"),
        "fcf_yield": vals.get("FCF Yield"),
        "beneish": vals.get("Beneish M-Score"),
        "short_ratio": vals.get("Short Ratio"),
        "insider_buying": vals.get("Insider Trans"),
    }
