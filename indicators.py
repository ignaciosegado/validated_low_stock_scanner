"""
indicators.py
=============
Pure price/volume technical analysis math. Stateless and side-effect free.
"""

import numpy as np
import pandas as pd
from typing import List


def true_range(df: pd.DataFrame) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close_prev = df["Close"].shift(1)
    return pd.concat(
        [high - low, (high - close_prev).abs(), (low - close_prev).abs()],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    tr = true_range(df)
    return tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def volume_sma(df: pd.DataFrame, window: int = 20) -> pd.Series:
    return df["Volume"].rolling(window=window, min_periods=window).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def find_swing_lows(df: pd.DataFrame, window: int = 5) -> List[int]:
    lows = df["Low"].values
    n = len(lows)
    swing_idx = []
    for i in range(window, n - window):
        segment = lows[i - window : i + window + 1]
        if lows[i] == segment.min():
            if i == window or lows[i] != lows[i - 1]:
                swing_idx.append(i)
    return swing_idx


def find_swing_highs(df: pd.DataFrame, window: int = 5) -> List[int]:
    highs = df["High"].values
    n = len(highs)
    swing_idx = []
    for i in range(window, n - window):
        segment = highs[i - window : i + window + 1]
        if highs[i] == segment.max():
            if i == window or highs[i] != highs[i - 1]:
                swing_idx.append(i)
    return swing_idx


def fibonacci_extension_levels(
    leg_start_price: float,
    leg_end_price: float,
    ratios: List[float],
) -> List[float]:
    leg_size = leg_start_price - leg_end_price
    if leg_size <= 0:
        return []
    return [leg_end_price + r * leg_size for r in ratios]


def dollar_volume(df: pd.DataFrame, window: int = 20) -> pd.Series:
    dv = df["Close"] * df["Volume"]
    return dv.rolling(window=window, min_periods=1).mean()


def pct_below_ma(close_price: float, ma_value: float) -> float:
    if pd.isna(ma_value) or ma_value <= 0:
        return 0.0
    diff = (ma_value - close_price) / ma_value
    return max(0.0, diff)


def ma_slope_pct(ma_series: pd.Series, as_of_idx: int, lookback_days: int) -> float:
    start_idx = as_of_idx - lookback_days
    if start_idx < 0:
        return 0.0
    ma_now = ma_series.iloc[as_of_idx]
    ma_then = ma_series.iloc[start_idx]
    if pd.isna(ma_now) or pd.isna(ma_then) or ma_then <= 0:
        return 0.0
    return (ma_now - ma_then) / ma_then


def is_fresh_multi_year_low(
    df: pd.DataFrame,
    low_idx: int,
    low_price: float,
    lookback_days: int,
) -> bool:
    start = max(0, low_idx - lookback_days)
    if start >= low_idx:
        return False
    prior_min = df["Low"].iloc[start:low_idx].min()
    if pd.isna(prior_min):
        return False
    return low_price <= prior_min * 1.001
