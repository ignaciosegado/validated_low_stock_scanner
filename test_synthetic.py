"""
test_synthetic.py
==================
Validates core validated-low detection against synthetic OHLCV series.
"""

import numpy as np
import pandas as pd

from signals import detect_validated_low
from config import StrategyConfig


def build_synthetic_series(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 250
    closes = np.zeros(n)
    volumes = np.zeros(n)

    closes[0:60] = np.linspace(80, 100, 60) + rng.normal(0, 0.5, 60)
    volumes[0:60] = rng.normal(1_000_000, 100_000, 60)

    closes[60:110] = np.linspace(100, 70, 50) + rng.normal(0, 0.7, 50)
    volumes[60:110] = rng.normal(2_500_000, 300_000, 50)

    closes[110:130] = np.linspace(70, 65, 20) + rng.normal(0, 0.3, 20)
    volumes[110:130] = np.linspace(1_800_000, 400_000, 20) + rng.normal(0, 50_000, 20)

    low_day = 127
    closes[low_day] = 64.0
    volumes[low_day] = 350_000

    closes[130:140] = np.linspace(65.5, 67, 10) + rng.normal(0, 0.2, 10)
    volumes[130:140] = rng.normal(500_000, 80_000, 10)

    closes[140:180] = np.linspace(67, 88, 40) + rng.normal(0, 0.5, 40)
    volumes[140:180] = rng.normal(1_200_000, 200_000, 40)

    closes[180:250] = 88 + rng.normal(0, 1.5, 70)
    volumes[180:250] = rng.normal(900_000, 150_000, 70)

    closes = np.clip(closes, 1, None)
    volumes = np.clip(volumes, 1000, None)

    highs = closes + np.abs(rng.normal(0.4, 0.2, n))
    lows = closes - np.abs(rng.normal(0.4, 0.2, n))
    opens = closes + rng.normal(0, 0.2, n)

    dates = pd.bdate_range(start="2024-01-02", periods=n)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes.astype(int)},
        index=dates,
    )


def run_test():
    df = build_synthetic_series()
    cfg = StrategyConfig()

    first_signal = None
    for as_of_idx in range(cfg.lookback_days, len(df)):
        sig = detect_validated_low(df, "TEST", cfg=cfg, as_of_idx=as_of_idx)
        if sig is not None:
            first_signal = sig
            break

    if first_signal is None:
        print("FAIL: No signal was detected at all.")
        return False

    print(first_signal.summary())
    checks = [
        ("Low price near constructed low (~64-67)", 63 <= first_signal.low_price <= 68),
        ("Stop is below the low", first_signal.stop_price < first_signal.low_price),
        ("Target is above entry", first_signal.target_price > first_signal.entry_price),
        ("R:R meets minimum threshold", first_signal.rr_ratio >= cfg.min_rr_ratio),
        ("Volume ratio at low is below threshold", first_signal.volume_ratio_at_low <= cfg.volume_ratio_max),
    ]

    all_pass = True
    for desc, passed in checks:
        if not passed:
            all_pass = False
        print(f"[{'PASS' if passed else 'FAIL'}] {desc}")
    return all_pass


def run_negative_test():
    rng = np.random.default_rng(7)
    n = 250
    closes = np.concatenate([
        np.linspace(80, 100, 60),
        np.linspace(100, 65, 70),
        np.linspace(65.5, 90, 60),
        np.full(60, 90),
    ]) + rng.normal(0, 0.3, n)
    volumes = np.concatenate([
        rng.normal(1_000_000, 100_000, 60),
        np.linspace(1_000_000, 4_000_000, 70),
        rng.normal(1_200_000, 200_000, 60),
        rng.normal(1_000_000, 100_000, 60),
    ])
    closes = np.clip(closes, 1, None)
    volumes = np.clip(volumes, 1000, None)
    df = pd.DataFrame(
        {"Open": closes.copy(), "High": closes + 0.4, "Low": closes - 0.4,
         "Close": closes, "Volume": volumes.astype(int)},
        index=pd.bdate_range(start="2024-01-02", periods=n),
    )

    cfg = StrategyConfig()
    any_signal = any(
        detect_validated_low(df, "NEGTEST", cfg=cfg, as_of_idx=i) is not None
        for i in range(cfg.lookback_days, len(df))
    )
    print(f"[{'PASS' if not any_signal else 'FAIL'}] Heavy-volume low rejected")
    return not any_signal


if __name__ == "__main__":
    pos = run_test()
    neg = run_negative_test()
    print("OVERALL:", "ALL TESTS PASSED" if (pos and neg) else "SOME TESTS FAILED")
