"""
universe.py
===========
Manages ticker universes. Loads either a user-supplied text file (one ticker
per line, ignoring '#' comments) or falls back to the cleaned universe in
tickers.py.
"""

from pathlib import Path
from typing import List, Optional

try:
    from tickers import tickers as DEFAULT_RAW_TICKERS
except ImportError:
    DEFAULT_RAW_TICKERS = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA",
        "SAN.MC", "IBE.MC", "ITX.MC", "BBVA.MC", "TEF.MC",
        "MC.PA", "OR.PA", "SIE.DE", "SAP.DE", "ASML.AS",
    ]


def _clean_tickers(raw_list: List[str]) -> List[str]:
    cleaned = []
    seen = set()
    for item in raw_list:
        t = str(item).strip().upper()
        if not t or t.startswith("#") or t in {"NONE", "NAN", "FALSE", "TRUE"}:
            continue
        if t not in seen:
            seen.add(t)
            cleaned.append(t)
    return cleaned


def load_universe(file_path: Optional[str] = None) -> List[str]:
    """
    Loads tickers from `file_path` if provided; otherwise returns the
    cleaned default universe from tickers.py.
    """
    if file_path is not None:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Universe file not found: {file_path}")
        lines = p.read_text(encoding="utf-8").splitlines()
        return _clean_tickers(lines)

    return _clean_tickers(DEFAULT_RAW_TICKERS)


def write_example_universe_file(path: str = "my_tickers.txt") -> None:
    sample = [
        "# Custom Watchlist (one Yahoo Finance ticker per line)",
        "# US Large Caps",
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL",
        "# Spain (IBEX 35)",
        "SAN.MC", "IBE.MC", "ITX.MC", "BBVA.MC", "AMS.MC",
        "# Europe",
        "ASML.AS", "SAP.DE", "SIE.DE", "MC.PA", "OR.PA",
    ]
    Path(path).write_text("\n".join(sample) + "\n", encoding="utf-8")
    print(f"Wrote sample universe file to {path}")
