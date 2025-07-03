import pyarrow.parquet as pq
import pandas as pd

from core.equity import EquityPortfolio

async def run_backtest(pf: EquityPortfolio, prices_file: str) -> pd.DataFrame:
    table = pq.read_table(prices_file)
    df = table.to_pandas()
    returns = df.pct_change().fillna(0)
    # simple cumulative return
    curve = (1 + returns).cumprod()
    return curve
