import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


@dataclass
class TechnicalSignal:
    symbol: str
    side: str            # "BUY" or "SELL"
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    rr: Decimal
    reason: str


def generate_signal(symbol: str, df: pd.DataFrame) -> Optional[TechnicalSignal]:
    """
    Very simple EMA-crossover signal, filtered by RSI, sized by ATR.
    Returns None when there's no setup. Returning None is the normal case.
    """
    if df is None or len(df) < 50:
        return None

    df = df.copy()
    df["ema_fast"] = ta.ema(df["close"], length=3)
    df["ema_slow"] = ta.ema(df["close"], length=5)
    df["rsi"] = ta.rsi(df["close"], length=14)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    # Drop rows where indicators are still warming up
    df = df.dropna(subset=["ema_fast", "ema_slow", "rsi", "atr"])
    if len(df) < 2:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    crossed_up = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
    crossed_down = prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]

    close = Decimal(str(last["close"]))
    atr = Decimal(str(last["atr"]))

    if atr <= 0:
        return None  # degenerate; skip

    if crossed_up and last["rsi"] < 70:
        sl = close - (atr * Decimal("1.5"))
        tp = close + (atr * Decimal("3.0"))
        return TechnicalSignal(
            symbol=symbol, side="BUY",
            entry=close, stop_loss=sl, take_profit=tp,
            rr=Decimal("2.0"),
            reason=f"EMA9 crossed above EMA21, RSI={last['rsi']:.1f}",
        )

    if crossed_down and last["rsi"] > 30:
        sl = close + (atr * Decimal("1.5"))
        tp = close - (atr * Decimal("3.0"))
        return TechnicalSignal(
            symbol=symbol, side="SELL",
            entry=close, stop_loss=sl, take_profit=tp,
            rr=Decimal("2.0"),
            reason=f"EMA9 crossed below EMA21, RSI={last['rsi']:.1f}",
        )

    return None