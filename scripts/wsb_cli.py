#!/usr/bin/env python3
"""WallStreetBets sentiment screener CLI."""

import argparse
from scrapers import wallstreetbets as wsb


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-universe", action="store_true")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    if args.refresh_universe:
        wsb.build_equity_universe()
        wsb.build_crypto_universe()
    else:
        df = wsb.run_analysis(args.days, args.top)
        if df.empty:
            print("No tickers found.")
        else:
            print(df.to_markdown(index=False))
