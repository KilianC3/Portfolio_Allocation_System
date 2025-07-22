#!/usr/bin/env python3
"""WallStreetBets sentiment screener CLI."""

import argparse
from scrapers import wallstreetbets as wsb


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--days", type=int, default=1, help="ignored; kept for backward compatibility"
    )
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    df = wsb.run_analysis(args.days, args.top)
    if df.empty:
        print("No tickers found.")
    else:
        print(df.to_markdown(index=False))
