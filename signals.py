"""
signals.py
==========
Core validated-low detection and risk/reward framing. Used identically
by scanner.py (live) and backtester.py (historical replay).
"""

from dataclasses import dataclass, field
from typing import Optional, List, Sequence
import pandas as pd

import indicators as ind
from config import StrategyConfig, DEFAULT_STRATEGY_CONFIG


@dataclass
class Signal:
    ticker: str
    as_of_date: pd.Timestamp
    low_date: pd.Timestamp
    low_price: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_per_share: float
    reward_per_share: float
    rr_ratio: float
    target_method: str
    volume_ratio_at_low: float
    risk_warnings: List[str] = field(default_factory=list)
    notes: str = ""

    def summary(self) -> str:
        base = (
            f"[{self.ticker}] as of {self.as_of_date.date()} | "
            f"low {self.low_price:.2f} on {self.low_date.date()} "
            f"(vol ratio {self.volume_ratio_at_low:.2f}) -> "
            f"entry {self.entry_price:.2f}, stop {self.stop_price:.2f} "
            f"(-{self.risk_per_share:.2f}), target {self.target_price:.2f} "
            f"(+{self.reward_per_share:.2f}), R:R {self.rr_ratio:.2f} "
            f"[{self.target_method}]"
        )
        if self.risk_warnings:
            base += "\n  ⚠ WARNINGS: " + "; ".join(self.risk_warnings)
        return base


def _nearest_resistance_above(
    df: pd.DataFrame,
    swing_high_idx: List[int],
    low_idx: int,
    price_floor: float,
    lookback_days: int,
) -> Optional[float]:
    start = max(0, low_idx - lookback_days)
    candidates = [
        df["High"].iloc[i]
        for i in swing_high_idx
        if start <= i <= low_idx and df["High"].iloc[i] > price_floor
    ]
    if not candidates:
        return None
    return min(candidates)


def _is_within_earnings_blackout(
    as_of_date: pd.Timestamp,
    earnings_dates: Optional[Sequence[pd.Timestamp]],
    blackout_days: int,
) -> bool:
    if not earnings_dates or blackout_days <= 0:
        return False
    current_day = pd.Timestamp(as_of_date).tz_localize(None).normalize()
    # Calendar-day buffer (~1.4x trading days) to catch upcoming announcements cleanly
    max_calendar_days = int(round(blackout_days * 1.45))
    for ed in earnings_dates:
        ed_norm = pd.Timestamp(ed).tz_localize(None).normalize()
        delta_days = (ed_norm - current_day).days
        if 0 <= delta_days <= max_calendar_days:
            return True
    return False


def detect_validated_low(
    df: pd.DataFrame,
    ticker: str,
    cfg: StrategyConfig = DEFAULT_STRATEGY_CONFIG,
    as_of_idx: Optional[int] = None,
    earnings_dates: Optional[Sequence[pd.Timestamp]] = None,
) -> Optional[Signal]:
    if as_of_idx is None:
        as_of_idx = len(df) - 1

    if as_of_idx < cfg.lookback_days:
        return None

    window_df = df.iloc[: as_of_idx + 1]
    as_of_date = window_df.index[as_of_idx]

    # --- Earnings blackout filter ---
    if cfg.enable_earnings_blackout and _is_within_earnings_blackout(
        as_of_date, earnings_dates, cfg.earnings_blackout_days
    ):
        return None

    sub = window_df.iloc[-cfg.lookback_days :]
    sub_offset = len(window_df) - len(sub)

    vol_avg = ind.volume_sma(window_df, cfg.volume_avg_window)
    atr_series = ind.atr(window_df, cfg.atr_window)

    swing_low_positions = ind.find_swing_lows(sub, window=cfg.swing_window)
    if not swing_low_positions:
        return None

    low_pos_in_sub = swing_low_positions[-1]
    low_pos = sub_offset + low_pos_in_sub

    days_since_low = as_of_idx - low_pos
    if days_since_low < cfg.swing_window or days_since_low > cfg.lookback_days:
        return None

    low_price = window_df["Low"].iloc[low_pos]
    low_date = window_df.index[low_pos]

    # --- Volume validation ---
    vol_at_low = window_df["Volume"].iloc[low_pos]
    avg_vol_at_low = vol_avg.iloc[low_pos]
    if pd.isna(avg_vol_at_low) or avg_vol_at_low <= 0:
        return None
    volume_ratio = vol_at_low / avg_vol_at_low
    if volume_ratio > cfg.volume_ratio_max:
        return None

    if cfg.require_declining_volume:
        d = cfg.decline_check_days
        if low_pos - 2 * d < 0:
            return None
        recent_avg = window_df["Volume"].iloc[low_pos - d : low_pos].mean()
        prior_avg = window_df["Volume"].iloc[low_pos - 2 * d : low_pos - d].mean()
        if prior_avg <= 0 or recent_avg >= prior_avg:
            return None

    # --- Stabilization check ---
    stabilize_slice = window_df["Close"].iloc[low_pos + 1 : as_of_idx + 1]
    if len(stabilize_slice) < cfg.stabilize_days:
        return None
    min_required = low_price * (1 + cfg.stabilize_min_pct_above_low)
    if (stabilize_slice < min_required).any():
        return None

    # --- Anti-chase filter ---
    current_close = window_df["Close"].iloc[as_of_idx]
    pct_above_low = (current_close - low_price) / low_price
    if pct_above_low > cfg.max_pct_above_low_for_entry:
        return None

    risk_warnings: List[str] = []

    if cfg.require_above_long_ma:
        ma_series = ind.sma(window_df["Close"], cfg.trend_filter_ma_window)
        ma_val = ma_series.iloc[as_of_idx]
        if pd.isna(ma_val) or current_close < ma_val:
            return None

    # --- Graduated severe-downtrend check ---
    if cfg.enable_downtrend_severity_check:
        ma_series = ind.sma(window_df["Close"], cfg.trend_filter_ma_window)
        ma_val = ma_series.iloc[as_of_idx]
        if not pd.isna(ma_val):
            pct_below = ind.pct_below_ma(current_close, ma_val)
            ma_slope = ind.ma_slope_pct(ma_series, as_of_idx, cfg.ma_slope_lookback_days)

            is_severe = (
                pct_below >= cfg.severe_downtrend_pct_below_ma
                and ma_slope <= -cfg.ma_falling_steeply_pct
            )
            if is_severe:
                warning = (
                    f"Severe downtrend: price is {pct_below:.0%} below its "
                    f"{cfg.trend_filter_ma_window}d MA (slope {ma_slope:+.0%} over "
                    f"{cfg.ma_slope_lookback_days}d)."
                )
                if cfg.severe_downtrend_action == "reject":
                    return None
                risk_warnings.append(warning)

    # --- Fresh multi-year low check ---
    if cfg.enable_fresh_low_check:
        if ind.is_fresh_multi_year_low(
            window_df, low_pos, low_price, cfg.fresh_low_lookback_days
        ):
            years = cfg.fresh_low_lookback_days / 252
            warning = (
                f"Fresh multi-year low: lowest price in ~{years:.0f} years "
                f"(no established prior support below)."
            )
            if cfg.fresh_low_action == "reject":
                return None
            risk_warnings.append(warning)

    # --- Liquidity & price floor ---
    if current_close < cfg.min_price:
        return None
    dv = ind.dollar_volume(window_df, cfg.volume_avg_window).iloc[as_of_idx]
    if pd.isna(dv) or dv < cfg.min_avg_dollar_volume:
        return None

    # --- Stop loss (minimum & maximum width bounds) ---
    atr_val = atr_series.iloc[as_of_idx]
    if pd.isna(atr_val) or atr_val <= 0:
        return None
    stop_price = low_price - cfg.atr_stop_multiplier * atr_val
    entry_price = current_close
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return None
    stop_dist_pct = risk_per_share / entry_price
    if stop_dist_pct < cfg.min_stop_pct or stop_dist_pct > cfg.max_stop_pct:
        return None

    # --- Price target over full resistance_lookback_days ---
    res_window_len = max(cfg.lookback_days, cfg.resistance_lookback_days)
    res_sub = window_df.iloc[-res_window_len:]
    res_offset = len(window_df) - len(res_sub)
    swing_high_positions_abs = [
        res_offset + p for p in ind.find_swing_highs(res_sub, window=cfg.swing_window)
    ]

    resistance_target = _nearest_resistance_above(
        window_df, swing_high_positions_abs, low_pos, entry_price, cfg.resistance_lookback_days
    )

    preceding_highs = [p for p in swing_high_positions_abs if p < low_pos]
    fib_target = None
    if preceding_highs:
        leg_start_price = window_df["High"].iloc[preceding_highs[-1]]
        fib_levels = ind.fibonacci_extension_levels(
            leg_start_price, low_price, cfg.fib_extension_levels
        )
        fib_candidates = [lvl for lvl in fib_levels if lvl > entry_price]
        if fib_candidates:
            fib_target = max(fib_candidates) if cfg.fib_take_further else min(fib_candidates)

    if resistance_target is not None and fib_target is not None:
        is_confluent = (
            abs(resistance_target - fib_target) / entry_price <= cfg.confluence_tolerance_pct
        )
        if not cfg.fib_take_further:
            if resistance_target <= fib_target:
                target_price = resistance_target
                target_method = "resistance+fib confluence" if is_confluent else "resistance"
            else:
                target_price = fib_target
                target_method = "resistance+fib confluence" if is_confluent else "fibonacci"
        else:
            if resistance_target >= fib_target:
                target_price = resistance_target
                target_method = "resistance+fib confluence" if is_confluent else "resistance"
            else:
                target_price = fib_target
                target_method = "resistance+fib confluence" if is_confluent else "fibonacci"
    elif resistance_target is not None:
        target_price = resistance_target
        target_method = "resistance"
    elif fib_target is not None:
        target_price = fib_target
        target_method = "fibonacci"
    else:
        return None

    # --- Target method filter ---
    if cfg.allowed_target_methods and target_method not in cfg.allowed_target_methods:
        return None

    reward_per_share = target_price - entry_price
    if reward_per_share <= 0:
        return None

    rr_ratio = reward_per_share / risk_per_share
    if rr_ratio < cfg.min_rr_ratio:
        return None

    return Signal(
        ticker=ticker,
        as_of_date=as_of_date,
        low_date=low_date,
        low_price=float(low_price),
        entry_price=float(entry_price),
        stop_price=float(stop_price),
        target_price=float(target_price),
        risk_per_share=float(risk_per_share),
        reward_per_share=float(reward_per_share),
        rr_ratio=float(rr_ratio),
        target_method=target_method,
        volume_ratio_at_low=float(volume_ratio),
        risk_warnings=risk_warnings,
    )