# Validated-Low Quant Scanner

Rule-based technical scanner and backtesting engine that detects swing lows formed on **low and declining volume** (seller exhaustion), frames ATR-buffered stops, and projects conservative targets from overhead resistance and Fibonacci extensions.

## Project Structure

- `config.py` — Strategy thresholds & portfolio backtest settings
- `universe.py` — Ticker universe loader & cleaner (integrates `tickers.py` or custom `.txt` files)
- `tickers.py` — Default US small/mid-cap ticker list
- `data.py` — `yfinance` historical OHLCV fetcher with local Parquet caching (`./cache/`)
- `indicators.py` — Stateless technical math (ATR, swing highs/lows, Fibonacci extensions, MA slope)
- `signals.py` — Core `detect_validated_low` engine shared identically by live scan and backtester
- `backtester.py` — Lookahead-free historical replay with next-open entry, gap-through fills, and max-position portfolio sizing
- `scanner.py` — Live scanner CLI
- `run_backtest.py` — Backtest CLI
- `test_synthetic.py` & `test_risk_filters.py` — Offline synthetic unit tests

## Quickstart

```bash
pip install -r requirements.txt

# 1. Verify offline unit tests
python3 test_synthetic.py
python3 test_risk_filters.py

# 2. Run 5-year portfolio backtest (max 10 concurrent positions, 1% risk/trade)
python3 run_backtest.py --period 5y --max-positions 10 --save backtest_trades.csv

# 3. Run today's live scan
python3 scanner.py --period 4y --save todays_scan.csv
```
