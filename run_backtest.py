"""
run_backtest.py
================
CLI entry point to backtest the validated-low strategy across the universe.
"""

import argparse
from dataclasses import replace

from universe import load_universe
from data import fetch_many, fetch_many_earnings
from backtester import backtest_universe
from config import DEFAULT_STRATEGY_CONFIG, DEFAULT_BACKTEST_CONFIG


def main():
    parser = argparse.ArgumentParser(description="Backtest the validated-low strategy.")
    parser.add_argument("--universe", type=str, default=None,
                         help="Path to a custom tickers file. Omit for the default universe.")
    parser.add_argument("--period", type=str, default="5y",
                         help="History length to fetch per ticker.")
    parser.add_argument("--min-rr", type=float, default=None,
                         help="Override the minimum risk:reward ratio filter.")
    parser.add_argument("--risk-pct", type=float, default=None,
                         help="Override per-trade risk as a fraction of capital (e.g. 0.01 = 1%%).")
    parser.add_argument("--max-positions", type=int, default=None,
                         help="Max concurrent open positions in portfolio simulation.")
    parser.add_argument("--save", type=str, default=None,
                         help="Path to save the full trade log as CSV.")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    strat_cfg = DEFAULT_STRATEGY_CONFIG
    if args.min_rr is not None:
        strat_cfg = replace(strat_cfg, min_rr_ratio=args.min_rr)

    bt_cfg = DEFAULT_BACKTEST_CONFIG
    if args.risk_pct is not None:
        bt_cfg = replace(bt_cfg, risk_per_trade_pct=args.risk_pct)
    if args.max_positions is not None:
        bt_cfg = replace(bt_cfg, max_concurrent_positions=args.max_positions)

    tickers = load_universe(args.universe)
    print(f"Backtesting {len(tickers)} tickers over period={args.period}...\n")

    data = fetch_many(tickers, period=args.period, use_cache=not args.no_cache)
    earnings_map = (
        fetch_many_earnings(list(data.keys()), use_cache=not args.no_cache)
        if strat_cfg.enable_earnings_blackout
        else None
    )
    print(f"\nFetched {len(data)}/{len(tickers)} tickers successfully.\n")

    report = backtest_universe(
        data, strat_cfg=strat_cfg, bt_cfg=bt_cfg, earnings_map=earnings_map
    )

    print("=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(report.summary())
    print()

    if report.n_trades < 30:
        print(
            "** CAUTION: fewer than 30 trades were generated. This sample\n"
            "** size is too small to draw reliable conclusions.\n"
        )

    if args.save:
        df = report.to_dataframe()
        df.to_csv(args.save, index=False)
        print(f"Full trade log saved to {args.save}")


if __name__ == "__main__":
    main()