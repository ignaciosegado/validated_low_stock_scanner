"""
test_risk_filters.py
=====================
Targeted tests for the severe-downtrend and fresh multi-year-low filters.
"""

import numpy as np
import pandas as pd
from dataclasses import replace

from signals import detect_validated_low
from config import StrategyConfig


def _make_df(closes, volumes, start="2020-01-02"):
    closes = np.clip(closes, 0.5, None)
    volumes = np.clip(volumes, 1000, None)
    dates = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {"Open": closes.copy(), "High": closes + 0.4, "Low": closes - 0.4,
         "Close": closes, "Volume": volumes.astype(int)},
        index=dates,
    )


def build_falling_knife() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    n = 500
    decline1 = np.linspace(200, 60, 300)
    bounce = np.linspace(60, 95, 30) + np.sin(np.linspace(0, 3, 30)) * 1.5
    decline2 = np.linspace(95, 45, 100)
    pause = np.linspace(45, 42, 20) + rng.normal(0, 0.3, 20)
    continued = np.linspace(42, 38, 50)
    closes = np.concatenate([decline1, bounce, decline2, pause, continued])[:n] + rng.normal(0, 0.5, n)

    vol_decline1 = np.linspace(3_000_000, 1_500_000, 300)
    vol_bounce = rng.normal(2_200_000, 200_000, 30)
    vol_decline2 = np.linspace(2_000_000, 1_000_000, 100)
    vol_pause = np.linspace(900_000, 250_000, 20)
    vol_continued = rng.normal(800_000, 100_000, 50)
    volumes = np.concatenate([vol_decline1, vol_bounce, vol_decline2, vol_pause, vol_continued])[:n] + rng.normal(0, 30_000, n)
    return _make_df(closes, volumes)


def build_range_bound_retest() -> pd.DataFrame:
    rng = np.random.default_rng(22)
    n = 400
    t = np.linspace(0, 8 * np.pi, n)
    closes = 85 + 15 * np.sin(t) + rng.normal(0, 1.0, n)
    closes[-40:-10] = np.linspace(85, 71, 30) + rng.normal(0, 0.3, 30)
    closes[-10:] = np.linspace(71, 74, 10) + rng.normal(0, 0.2, 10)
    volumes = rng.normal(1_000_000, 150_000, n)
    volumes[-15:-5] = np.linspace(900_000, 250_000, 10)
    volumes[-5:] = rng.normal(400_000, 50_000, 5)
    return _make_df(closes, volumes)


def build_fresh_breakdown() -> pd.DataFrame:
    rng = np.random.default_rng(33)
    n = 400
    t = np.linspace(0, 6 * np.pi, n - 60)
    range_bound = 90 + 10 * np.sin(t) + rng.normal(0, 1.0, n - 60)
    breakdown = np.linspace(85, 60, 40) + rng.normal(0, 0.5, 40)
    stabilize = np.linspace(60.5, 63, 20) + rng.normal(0, 0.2, 20)
    closes = np.concatenate([range_bound, breakdown, stabilize])

    vol_range = rng.normal(1_000_000, 150_000, n - 60)
    vol_breakdown = np.linspace(2_000_000, 600_000, 40)
    vol_stabilize = rng.normal(400_000, 50_000, 20)
    volumes = np.concatenate([vol_range, vol_breakdown, vol_stabilize])
    return _make_df(closes, volumes)


def scan_all_signals(df, ticker, cfg):
    seen_low_dates = set()
    signals = []
    for as_of_idx in range(cfg.lookback_days, len(df)):
        sig = detect_validated_low(df, ticker, cfg=cfg, as_of_idx=as_of_idx)
        if sig is not None and sig.low_date not in seen_low_dates:
            seen_low_dates.add(sig.low_date)
            signals.append(sig)
    return signals


if __name__ == "__main__":
    df_knife = build_falling_knife()
    r1 = len(scan_all_signals(df_knife, "KNIFE", StrategyConfig())) == 0
    sigs_flagged = scan_all_signals(df_knife, "KNIFE", replace(StrategyConfig(), severe_downtrend_action="flag"))
    r2 = any("Severe downtrend" in w for s in sigs_flagged for w in s.risk_warnings)

    df_bd = build_fresh_breakdown()
    sigs_bd = scan_all_signals(df_bd, "BD", replace(StrategyConfig(), fresh_low_action="flag", severe_downtrend_action="flag"))
    r3 = any("Fresh multi-year low" in w for s in sigs_bd for w in s.risk_warnings)

    print(f"[{'PASS' if r1 else 'FAIL'}] Falling knife rejected by default")
    print(f"[{'PASS' if r2 else 'FAIL'}] Falling knife flagged when set to flag")
    print(f"[{'PASS' if r3 else 'FAIL'}] Fresh breakdown triggers fresh-low warning")
    print("OVERALL:", "ALL TESTS PASSED" if all([r1, r2, r3]) else "SOME TESTS FAILED")
