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
    side: str
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    rr: Decimal
    score: int
    total_checks: int
    checklist: list[str]
    reason: str


def _find_col(df: pd.DataFrame, prefix: str) -> Optional[str]:
    """Find a column by prefix, since pandas_ta float suffixes vary
    (e.g. 'BBU_20_2.0' vs 'BBU_20_2')."""
    for c in df.columns:
        if c.startswith(prefix):
            return c
    return None


def generate_signal(symbol: str, df: pd.DataFrame) -> Optional[TechnicalSignal]:
    """
    10-point confluence checklist triggered by a 9/21 EMA crossover.
    Advanced screener for manual trade execution.
    """
    if df is None or len(df) < 200:
        return None

    df = df.copy()

    # Moving averages — names MUST match the reads below
    df["ema_9"]   = ta.ema(df["close"], length=9)
    df["ema_21"]  = ta.ema(df["close"], length=21)
    df["ema_50"]  = ta.ema(df["close"], length=50)
    df["ema_200"] = ta.ema(df["close"], length=200)

    # Momentum & volatility
    df["rsi"] = ta.rsi(df["close"], length=14)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    df["atr_sma"] = ta.sma(df["atr"], length=14)

    # MACD and Bollinger Bands
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    bbands = ta.bbands(df["close"], length=20, std=2)
    df = pd.concat([df, bbands], axis=1)

    # Resolve pandas_ta column names defensively
    macd_line = _find_col(df, "MACD_12_26_9")
    macd_sig  = _find_col(df, "MACDs_12_26_9")
    macd_hist = _find_col(df, "MACDh_12_26_9")
    bb_upper  = _find_col(df, "BBU_20")
    bb_lower  = _find_col(df, "BBL_20")
    if not all([macd_line, macd_sig, macd_hist, bb_upper, bb_lower]):
        logger.warning("Indicator columns missing for %s: %s", symbol, list(df.columns))
        return None

    df = df.dropna()
    if len(df) < 2:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    crossed_up   = prev["ema_9"] <= prev["ema_21"] and last["ema_9"] > last["ema_21"]
    crossed_down = prev["ema_9"] >= prev["ema_21"] and last["ema_9"] < last["ema_21"]
    if not crossed_up and not crossed_down:
        return None

    close = Decimal(str(last["close"]))
    atr = Decimal(str(last["atr"]))
    if atr <= 0:
        return None

    score = 0
    checklist: list[str] = []
    total_checks = 10

    if crossed_up:
        score += 1
        checklist.append("✅ EMA 9 crossed above 21")

        if last["close"] > last["ema_200"]:
            score += 1; checklist.append("✅ Price > 200 EMA (Macro Bullish)")
        else:
            checklist.append("❌ Price < 200 EMA (Counter-trend)")

        if last["close"] > last["ema_50"]:
            score += 1; checklist.append("✅ Price > 50 EMA (Mid Bullish)")
        else:
            checklist.append("❌ Price < 50 EMA")

        if 40 < last["rsi"] < 65:
            score += 1; checklist.append(f"✅ RSI in optimal zone ({last['rsi']:.1f})")
        else:
            checklist.append(f"❌ RSI sub-optimal ({last['rsi']:.1f})")

        if last["rsi"] > prev["rsi"]:
            score += 1; checklist.append("✅ RSI is rising")
        else:
            checklist.append("❌ RSI is falling")

        if last[macd_hist] > 0:
            score += 1; checklist.append("✅ MACD Histogram is Bullish")
        else:
            checklist.append("❌ MACD Histogram is Bearish")

        if last[macd_line] > last[macd_sig]:
            score += 1; checklist.append("✅ MACD > Signal Line")
        else:
            checklist.append("❌ MACD < Signal Line")

        if last["atr"] > last["atr_sma"]:
            score += 1; checklist.append("✅ ATR above average (Expanding volatility)")
        else:
            checklist.append("❌ ATR below average (Low volatility)")

        if last["close"] < last[bb_upper]:
            score += 1; checklist.append("✅ Price not overextended (Below Upper BB)")
        else:
            checklist.append("❌ Price overextended (Above Upper BB)")

        if last["close"] > last["open"]:
            score += 1; checklist.append("✅ Trigger candle closed bullish")
        else:
            checklist.append("❌ Trigger candle closed bearish")

        sl = close - (atr * Decimal("1.5"))
        tp = close + (atr * Decimal("3.0"))
        return TechnicalSignal(
            symbol=symbol, side="BUY", entry=close, stop_loss=sl, take_profit=tp,
            rr=Decimal("2.0"), score=score, total_checks=total_checks,
            checklist=checklist, reason="EMA 9/21 Bullish Cross",
        )

    # crossed_down
    score += 1
    checklist.append("✅ EMA 9 crossed below 21")

    if last["close"] < last["ema_200"]:
        score += 1; checklist.append("✅ Price < 200 EMA (Macro Bearish)")
    else:
        checklist.append("❌ Price > 200 EMA (Counter-trend)")

    if last["close"] < last["ema_50"]:
        score += 1; checklist.append("✅ Price < 50 EMA (Mid Bearish)")
    else:
        checklist.append("❌ Price > 50 EMA")

    if 35 < last["rsi"] < 60:
        score += 1; checklist.append(f"✅ RSI in optimal zone ({last['rsi']:.1f})")
    else:
        checklist.append(f"❌ RSI sub-optimal ({last['rsi']:.1f})")

    if last["rsi"] < prev["rsi"]:
        score += 1; checklist.append("✅ RSI is falling")
    else:
        checklist.append("❌ RSI is rising")

    if last[macd_hist] < 0:
        score += 1; checklist.append("✅ MACD Histogram is Bearish")
    else:
        checklist.append("❌ MACD Histogram is Bullish")

    if last[macd_line] < last[macd_sig]:
        score += 1; checklist.append("✅ MACD < Signal Line")
    else:
        checklist.append("❌ MACD > Signal Line")

    if last["atr"] > last["atr_sma"]:
        score += 1; checklist.append("✅ ATR above average (Expanding volatility)")
    else:
        checklist.append("❌ ATR below average (Low volatility)")

    if last["close"] > last[bb_lower]:
        score += 1; checklist.append("✅ Price not overextended (Above Lower BB)")
    else:
        checklist.append("❌ Price overextended (Below Lower BB)")

    if last["close"] < last["open"]:
        score += 1; checklist.append("✅ Trigger candle closed bearish")
    else:
        checklist.append("❌ Trigger candle closed bullish")

    sl = close + (atr * Decimal("1.5"))
    tp = close - (atr * Decimal("3.0"))
    return TechnicalSignal(
        symbol=symbol, side="SELL", entry=close, stop_loss=sl, take_profit=tp,
        rr=Decimal("2.0"), score=score, total_checks=total_checks,
        checklist=checklist, reason="EMA 9/21 Bearish Cross",
    )