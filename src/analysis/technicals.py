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

def generate_signal(symbol: str, df: pd.DataFrame) -> Optional[TechnicalSignal]:
    """
    Evaluates a 10-point confluence checklist triggered by a 9/21 EMA crossover.
    Acts as an advanced screener for manual trade execution.
    """
    # Require enough data to calculate the 200 EMA
    if df is None or len(df) < 200:
        return None

    df = df.copy()

    # Calculate Moving Averages
    df["ema_9"] = ta.ema(df["close"], length=9)
    df["ema_21"] = ta.ema(df["close"], length=21)
    df["ema_50"] = ta.ema(df["close"], length=50)
    df["ema_200"] = ta.ema(df["close"], length=200)
    
    # Calculate Momentum & Volatility
    df["rsi"] = ta.rsi(df["close"], length=14)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    df["atr_sma"] = ta.sma(df["atr"], length=14) # To check if volatility is expanding

    # Calculate MACD (Outputs: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)

    # Calculate Bollinger Bands (Outputs: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0, etc.)
    bbands = ta.bbands(df["close"], length=20, std=2)
    df = pd.concat([df, bbands], axis=1)

    # Clean up and ensure we have recent data
    df = df.dropna()
    if len(df) < 2:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Baseline Trigger: The actual Crossover
    crossed_up = prev["ema_9"] <= prev["ema_21"] and last["ema_9"] > last["ema_21"]
    crossed_down = prev["ema_9"] >= prev["ema_21"] and last["ema_9"] < last["ema_21"]

    if not crossed_up and not crossed_down:
        return None

    close = Decimal(str(last["close"]))
    atr = Decimal(str(last["atr"]))

    if atr <= 0:
        return None

    score = 0
    checklist = []
    total_checks = 10

    # ---------------------------------------------------------
    # BUY SIGNAL EVALUATION
    # ---------------------------------------------------------
    if crossed_up:
        # 1. Baseline
        score += 1
        checklist.append("✅ EMA 9 crossed above 21")

        # 2. Macro Trend
        if last["close"] > last["ema_200"]:
            score += 1
            checklist.append("✅ Price > 200 EMA (Macro Bullish)")
        else:
            checklist.append("❌ Price < 200 EMA (Counter-trend)")

        # 3. Mid Trend
        if last["close"] > last["ema_50"]:
            score += 1
            checklist.append("✅ Price > 50 EMA (Mid Bullish)")
        else:
            checklist.append("❌ Price < 50 EMA")

        # 4. RSI Zone (Room to run)
        if 40 < last["rsi"] < 65:
            score += 1
            checklist.append(f"✅ RSI in optimal zone ({last['rsi']:.1f})")
        else:
            checklist.append(f"❌ RSI sub-optimal ({last['rsi']:.1f})")

        # 5. RSI Momentum
        if last["rsi"] > prev["rsi"]:
            score += 1
            checklist.append("✅ RSI is rising")
        else:
            checklist.append("❌ RSI is falling")

        # 6. MACD Histogram
        if last["MACDh_12_26_9"] > 0:
            score += 1
            checklist.append("✅ MACD Histogram is Bullish")
        else:
            checklist.append("❌ MACD Histogram is Bearish")

        # 7. MACD Line Cross
        if last["MACD_12_26_9"] > last["MACDs_12_26_9"]:
            score += 1
            checklist.append("✅ MACD > Signal Line")
        else:
            checklist.append("❌ MACD < Signal Line")

        # 8. Volatility Expanding
        if last["atr"] > last["atr_sma"]:
            score += 1
            checklist.append("✅ ATR above average (Expanding volatility)")
        else:
            checklist.append("❌ ATR below average (Low volatility)")

        # 9. Bollinger Band Extrema
        if last["close"] < last["BBU_20_2.0"]:
            score += 1
            checklist.append("✅ Price not overextended (Below Upper BB)")
        else:
            checklist.append("❌ Price overextended (Above Upper BB)")

        # 10. Candle Close
        if last["close"] > last["open"]:
            score += 1
            checklist.append("✅ Trigger candle closed bullish")
        else:
            checklist.append("❌ Trigger candle closed bearish")

        sl = close - (atr * Decimal("1.5"))
        tp = close + (atr * Decimal("3.0"))

        return TechnicalSignal(
            symbol=symbol, side="BUY",
            entry=close, stop_loss=sl, take_profit=tp,
            rr=Decimal("2.0"),
            score=score,
            total_checks=total_checks,
            checklist=checklist,
            reason="EMA 9/21 Bullish Cross"
        )

    # ---------------------------------------------------------
    # SELL SIGNAL EVALUATION
    # ---------------------------------------------------------
    if crossed_down:
        # 1. Baseline
        score += 1
        checklist.append("✅ EMA 9 crossed below 21")

        # 2. Macro Trend
        if last["close"] < last["ema_200"]:
            score += 1
            checklist.append("✅ Price < 200 EMA (Macro Bearish)")
        else:
            checklist.append("❌ Price > 200 EMA (Counter-trend)")

        # 3. Mid Trend
        if last["close"] < last["ema_50"]:
            score += 1
            checklist.append("✅ Price < 50 EMA (Mid Bearish)")
        else:
            checklist.append("❌ Price > 50 EMA")

        # 4. RSI Zone
        if 35 < last["rsi"] < 60:
            score += 1
            checklist.append(f"✅ RSI in optimal zone ({last['rsi']:.1f})")
        else:
            checklist.append(f"❌ RSI sub-optimal ({last['rsi']:.1f})")

        # 5. RSI Momentum
        if last["rsi"] < prev["rsi"]:
            score += 1
            checklist.append("✅ RSI is falling")
        else:
            checklist.append("❌ RSI is rising")

        # 6. MACD Histogram
        if last["MACDh_12_26_9"] < 0:
            score += 1
            checklist.append("✅ MACD Histogram is Bearish")
        else:
            checklist.append("❌ MACD Histogram is Bullish")

        # 7. MACD Line Cross
        if last["MACD_12_26_9"] < last["MACDs_12_26_9"]:
            score += 1
            checklist.append("✅ MACD < Signal Line")
        else:
            checklist.append("❌ MACD > Signal Line")

        # 8. Volatility Expanding
        if last["atr"] > last["atr_sma"]:
            score += 1
            checklist.append("✅ ATR above average (Expanding volatility)")
        else:
            checklist.append("❌ ATR below average (Low volatility)")

        # 9. Bollinger Band Extrema
        if last["close"] > last["BBL_20_2.0"]:
            score += 1
            checklist.append("✅ Price not overextended (Above Lower BB)")
        else:
            checklist.append("❌ Price overextended (Below Lower BB)")

        # 10. Candle Close
        if last["close"] < last["open"]:
            score += 1
            checklist.append("✅ Trigger candle closed bearish")
        else:
            checklist.append("❌ Trigger candle closed bullish")

        sl = close + (atr * Decimal("1.5"))
        tp = close - (atr * Decimal("3.0"))

        return TechnicalSignal(
            symbol=symbol, side="SELL",
            entry=close, stop_loss=sl, take_profit=tp,
            rr=Decimal("2.0"),
            score=score,
            total_checks=total_checks,
            checklist=checklist,
            reason="EMA 9/21 Bearish Cross"
        )

    return None