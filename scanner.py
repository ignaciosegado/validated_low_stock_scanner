"""
scanner.py
==========
Live scan CLI for validated-low technical setups.
"""

import argparse
from dataclasses import replace
from datetime import datetime
import pandas as pd

from universe import load_universe
from data import fetch_many, fetch_many_earnings
from signals import detect_validated_low
from config import (
    StrategyConfig,
    BacktestConfig,
    DEFAULT_STRATEGY_CONFIG,
    DEFAULT_BACKTEST_CONFIG,
)


def scan(
    tickers,
    cfg: StrategyConfig = DEFAULT_STRATEGY_CONFIG,
    period: str = "4y",
    use_cache: bool = True,
) -> list:
    print(f"Fetching data for {len(tickers)} tickers (period={period})...")
    data = fetch_many(tickers, period=period, use_cache=use_cache)
    earnings_map = (
        fetch_many_earnings(list(data.keys()), use_cache=use_cache)
        if cfg.enable_earnings_blackout
        else {}
    )
    print(f"Successfully fetched {len(data)}/{len(tickers)} tickers.\n")

    signals = []
    for ticker, df in data.items():
        try:
            sig = detect_validated_low(
                df, ticker, cfg=cfg, earnings_dates=earnings_map.get(ticker)
            )
            if sig is not None:
                signals.append(sig)
        except Exception as e:
            print(f"[scanner] Error evaluating {ticker}: {e}")

    signals.sort(key=lambda s: s.rr_ratio, reverse=True)
    return signals


def print_report(
    signals: list,
    cfg: StrategyConfig,
    bt_cfg: BacktestConfig = DEFAULT_BACKTEST_CONFIG,
) -> None:
    print("=" * 78)
    print(f"SCAN REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 78)

    if not signals:
        print(
            "\nNo setups currently meet all filter criteria.\n"
            f"Run again in a few days (min R:R = {cfg.min_rr_ratio}).\n"
        )
        return

    print(f"\n{len(signals)} candidate(s) found:\n")
    for sig in signals:
        min_open = sig.entry_price * (1 - bt_cfg.max_gap_down_pct)
        print("-" * 78)
        print(sig.summary())
        print(
            f"  Risk: {sig.risk_per_share / sig.entry_price:.1%} of entry price | "
            f"Target method: {sig.target_method} | "
            f"Min next open: {min_open:.2f} (abort if open gaps below)"
        )
    print("-" * 78)


def save_report(
    signals: list,
    path: str = "scan_results.csv",
    bt_cfg: BacktestConfig = DEFAULT_BACKTEST_CONFIG,
) -> None:
    if not signals:
        return
    rows = [
        {
            "ticker": s.ticker,
            "as_of_date": s.as_of_date,
            "low_date": s.low_date,
            "low_price": s.low_price,
            "entry_price": s.entry_price,
            "min_next_open": round(s.entry_price * (1 - bt_cfg.max_gap_down_pct), 4),
            "stop_price": s.stop_price,
            "target_price": s.target_price,
            "risk_per_share": s.risk_per_share,
            "reward_per_share": s.reward_per_share,
            "rr_ratio": s.rr_ratio,
            "target_method": s.target_method,
            "volume_ratio_at_low": s.volume_ratio_at_low,
            "risk_warnings": " | ".join(s.risk_warnings) if s.risk_warnings else "",
        }
        for s in signals
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    print(f"Saved results to {path}")


def main():
    parser = argparse.ArgumentParser(description="Scan for validated-low technical setups.")
    parser.add_argument("--universe", type=str, default=None,
                         help="Path to a custom tickers file (one ticker per line).")
    parser.add_argument("--period", type=str, default="4y",
                         help="History length to fetch per ticker (default 4y to cover 3y fresh-low check).")
    parser.add_argument("--min-rr", type=float, default=None,
                         help="Override the minimum risk:reward ratio filter.")
    parser.add_argument("--no-cache", action="store_true",
                         help="Force a fresh download, ignoring any cached data.")
    parser.add_argument("--save", type=str, default=None,
                         help="Path to save results as CSV (optional).")
    args = parser.parse_args()

    cfg = DEFAULT_STRATEGY_CONFIG
    if args.min_rr is not None:
        cfg = replace(cfg, min_rr_ratio=args.min_rr)

    tickers = load_universe(args.universe)
    signals = scan(tickers, cfg=cfg, period=args.period, use_cache=not args.no_cache)
    print_report(signals, cfg)

    if args.save:
        save_report(signals, args.save)


if __name__ == "__main__":
    main()