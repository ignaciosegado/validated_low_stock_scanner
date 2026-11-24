"""
config.py
=========
Every tunable parameter for the strategy and portfolio simulation lives here.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class StrategyConfig:
    # ----- Swing low / "validated low" detection -----
    swing_window: int = 5
    lookback_days: int = 120

    # Volume validation: true bottom forms on light, drying-up volume
    volume_avg_window: int = 20
    volume_ratio_max: float = 0.85

    require_declining_volume: bool = True
    decline_check_days: int = 5

    # Stabilization after the low
    stabilize_days: int = 3
    stabilize_min_pct_above_low: float = 0.0

    # ----- ATR & Stop Loss -----
    atr_window: int = 14
    atr_stop_multiplier: float = 0.5
    min_stop_pct: float = 0.020  # 2.0% min stop distance (avoids intraday noise stop-outs)
    max_stop_pct: float = 0.080  # 8.0% max stop distance

    # ----- Price Target -----
    resistance_lookback_days: int = 250
    fib_extension_levels: List[float] = field(
        default_factory=lambda: [0.618, 1.0, 1.272, 1.618]
    )
    fib_take_further: bool = False
    confluence_tolerance_pct: float = 0.015  # 1.5% tolerance to claim confluence
    allowed_target_methods: List[str] = field(
        default_factory=lambda: ["fibonacci"]
    )

    # ----- Risk/Reward & Entry -----
    min_rr_ratio: float = 2.0
    max_pct_above_low_for_entry: float = 0.06  # 6% max chase from low

    # ----- Trend / Value-Trap Filters -----
    trend_filter_ma_window: int = 200
    require_above_long_ma: bool = False

    enable_downtrend_severity_check: bool = True
    severe_downtrend_pct_below_ma: float = 0.30
    ma_slope_lookback_days: int = 60
    ma_falling_steeply_pct: float = 0.05
    severe_downtrend_action: str = "reject"  # "reject" or "flag"

    enable_fresh_low_check: bool = True
    fresh_low_lookback_days: int = 756  # ~3 trading years
    fresh_low_action: str = "flag"  # Keep multi-year capitulation bounces enabled

    # ----- Earnings Event Filter -----
    enable_earnings_blackout: bool = True
    earnings_blackout_days: int = 7  # Skip entries within 7 trading days before earnings

    # ----- Liquidity & Price Floors -----
    min_avg_dollar_volume: float = 1_000_000  # $1M/day
    min_price: float = 5.0


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    risk_per_trade_pct: float = 0.01       # 1% equity risk per trade
    max_concurrent_positions: int = 10     # Caps total portfolio heat at ~10%
    max_holding_days: int = 90
    commission_pct: float = 0.0005         # 5 bps per side
    slippage_pct: float = 0.0005           # 5 bps per side
    entry_on_next_open: bool = True        # True = realistic EOD scan -> next Open entry
    max_gap_down_pct: float = 0.002        # Abort entry if next open gaps down > 0.2%
    recheck_min_rr_at_open: bool = True    # Require R:R >= min_rr_ratio at actual open price


DEFAULT_STRATEGY_CONFIG = StrategyConfig()
DEFAULT_BACKTEST_CONFIG = BacktestConfig()