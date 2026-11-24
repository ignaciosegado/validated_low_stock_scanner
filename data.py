"""
data.py
=======
Handles fetching OHLCV data and earnings dates via yfinance, with local on-disk parquet caching.
"""

from pathlib import Path
from typing import Optional, Dict, List
import time

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

CACHE_DIR = Path(__file__).parent / "cache"


def _cache_path(ticker: str, suffix: str = "") -> Path:
    safe_name = ticker.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / f"{safe_name}{suffix}.parquet"


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_history(
    ticker: str,
    period: str = "4y",
    use_cache: bool = True,
    max_cache_age_days: int = 1,
    retries: int = 3,
    retry_delay_sec: float = 2.0,
) -> Optional[pd.DataFrame]:
    if yf is None:
        raise RuntimeError("yfinance is not installed. Run: pip install yfinance")

    _ensure_cache_dir()
    cache_file = _cache_path(ticker)

    cached_df = None
    if use_cache and cache_file.exists():
        try:
            cached_df = pd.read_parquet(cache_file)
            if not cached_df.empty:
                last_date = cached_df.index.max()
                age_days = (pd.Timestamp.now(tz=last_date.tz) - last_date).days
                if age_days <= max_cache_age_days:
                    return cached_df
        except Exception:
            cached_df = None

    last_err = None
    for attempt in range(retries):
        try:
            df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
            if df is None or df.empty:
                last_err = ValueError("empty dataframe returned")
                time.sleep(retry_delay_sec)
                continue

            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df = df.dropna(subset=["Close"])

            if use_cache:
                try:
                    df.to_parquet(cache_file)
                except Exception as e:
                    print(f"[data] Warning: could not write cache for {ticker}: {e}")

            return df

        except Exception as e:
            last_err = e
            time.sleep(retry_delay_sec)

    print(f"[data] Failed to fetch {ticker} after {retries} attempts: {last_err}")
    if cached_df is not None and not cached_df.empty:
        print(f"[data] Using stale cached data for {ticker} instead.")
        return cached_df
    return None


def fetch_earnings_dates(
    ticker: str,
    use_cache: bool = True,
    max_cache_age_days: int = 7,
) -> List[pd.Timestamp]:
    """
    Fetches historical and upcoming earnings announcement dates (normalized to date)
    to prevent entering right before binary overnight earnings gaps.
    """
    if yf is None:
        return []

    _ensure_cache_dir()
    cache_file = _cache_path(ticker, suffix="_earnings")

    if use_cache and cache_file.exists():
        try:
            cached = pd.read_parquet(cache_file)
            age_days = (pd.Timestamp.now() - pd.Timestamp(cache_file.stat().st_mtime, unit="s")).days
            if age_days <= max_cache_age_days and "earnings_date" in cached.columns:
                return list(pd.to_datetime(cached["earnings_date"]).dt.tz_localize(None).dt.normalize())
        except Exception:
            pass

    try:
        ed = yf.Ticker(ticker).get_earnings_dates(limit=24)
        if ed is None or ed.empty:
            return []
        dates = pd.to_datetime(ed.index).tz_localize(None).normalize().unique().sort_values()
        if use_cache:
            try:
                pd.DataFrame({"earnings_date": dates}).to_parquet(cache_file)
            except Exception:
                pass
        return list(dates)
    except Exception:
        return []


def fetch_many(
    tickers,
    period: str = "4y",
    use_cache: bool = True,
    max_cache_age_days: int = 1,
    progress: bool = True,
) -> Dict[str, pd.DataFrame]:
    results: Dict[str, pd.DataFrame] = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        if progress:
            print(f"[data] ({i}/{total}) fetching {ticker}...")
        df = fetch_history(
            ticker,
            period=period,
            use_cache=use_cache,
            max_cache_age_days=max_cache_age_days,
        )
        if df is not None and len(df) > 0:
            results[ticker] = df
    return results


def fetch_many_earnings(
    tickers,
    use_cache: bool = True,
    max_cache_age_days: int = 7,
) -> Dict[str, List[pd.Timestamp]]:
    return {
        ticker: fetch_earnings_dates(
            ticker, use_cache=use_cache, max_cache_age_days=max_cache_age_days
        )
        for ticker in tickers
    }