import logging
from typing import Optional
import httpx
import pandas as pd
from src.config import settings

logger = logging.getLogger(__name__)

# Twelve Data symbol format:
#   forex: "EUR/USD", "GBP/USD"
#   crypto: "BTC/USD", "ETH/USD"
#   stocks: "AAPL", "MSFT"
# Intervals: 1min, 5min, 15min, 30min, 1h, 4h, 1day

def get_recent_bars(
    symbol: str,
    interval: str = "5min",
    outputsize: int = 100,
) -> pd.DataFrame:
    """
    Fetch recent OHLCV bars from Twelve Data.
    Returns a DataFrame with columns: open, high, low, close, volume.
    Index is a UTC DatetimeIndex, oldest -> newest.
    """
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": settings.twelvedata_api_key,
        "format": "JSON",
    }
    try:
        r = httpx.get(url, params=params, timeout=10.0)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError as e:
        logger.exception("HTTP error fetching %s: %s", symbol, e)
        return pd.DataFrame()

    if data.get("status") == "error":
        logger.warning("Twelve Data error for %s: %s", symbol, data.get("message"))
        return pd.DataFrame()

    values = data.get("values")
    if not values:
        logger.warning("No values for %s", symbol)
        return pd.DataFrame()

    df = pd.DataFrame(values)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.set_index("datetime").sort_index()
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = 0  # forex doesn't have real volume
    return df[["open", "high", "low", "close", "volume"]].dropna()

def get_current_price(symbol: str) -> Optional[float]:
    """Fetch the latest price for a symbol. Returns None on failure."""
    url = "https://api.twelvedata.com/price"
    params = {"symbol": symbol, "apikey": settings.twelvedata_api_key}
    try:
        r = httpx.get(url, params=params, timeout=10.0)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError as e:
        logger.exception("Price fetch failed for %s: %s", symbol, e)
        return None

    if "price" not in data:
        logger.warning("No price for %s: %s", symbol, data)
        return None
    return float(data["price"])