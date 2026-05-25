import numpy as np
import pandas as pd
from src.analysis.technicals import generate_signal


def _fake_bars(values):
    n = len(values)
    idx = pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame({
        "open":   values,
        "high":   [v + 0.0005 for v in values],
        "low":    [v - 0.0005 for v in values],
        "close":  values,
        "volume": [0] * n,
    }, index=idx)


def _scan_for_signal(df, side):
    """Slide through the data; return the first signal of the given side, or None."""
    for i in range(50, len(df) + 1):
        sig = generate_signal("EUR/USD", df.iloc[:i])
        if sig is not None and sig.side == side:
            return sig
    return None


def test_no_signal_on_flat_market():
    df = _fake_bars([1.1000] * 100)
    assert generate_signal("EUR/USD", df) is None


def test_buy_signal_during_uptrend_reversal():
    # Long downtrend establishes EMA9 < EMA21, then a strong uptrend forces a cross.
    # Noise prevents idealized indicator behavior that breaks the RSI filter.
    rng = np.random.default_rng(42)
    down = np.linspace(1.1100, 1.0900, 80) + rng.normal(0, 0.0003, 80)
    up   = np.linspace(1.0900, 1.1200, 80) + rng.normal(0, 0.0003, 80)
    df = _fake_bars(list(down) + list(up))
    sig = _scan_for_signal(df, "BUY")
    assert sig is not None, "Expected a BUY signal somewhere during the reversal"
    assert sig.stop_loss < sig.entry < sig.take_profit


def test_sell_signal_during_downtrend_reversal():
    rng = np.random.default_rng(42)
    up   = np.linspace(1.0900, 1.1100, 80) + rng.normal(0, 0.0003, 80)
    down = np.linspace(1.1100, 1.0800, 80) + rng.normal(0, 0.0003, 80)
    df = _fake_bars(list(up) + list(down))
    sig = _scan_for_signal(df, "SELL")
    assert sig is not None, "Expected a SELL signal somewhere during the reversal"
    assert sig.take_profit < sig.entry < sig.stop_loss