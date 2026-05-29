import logging
from dataclasses import dataclass, asdict, field
import pandas as pd
import pandas_ta_classic as ta

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    symbol: str
    timeframe: str
    price: float
    trend: str                       # bullish | bearish | ranging
    structure: str                   # plain-English HH/HL description
    support: list[float] = field(default_factory=list)
    resistance: list[float] = field(default_factory=list)
    psychological: list[float] = field(default_factory=list)
    rsi: float = 0.0
    rsi_state: str = "neutral"
    ema_alignment: str = ""
    divergence: str = "none"         # bullish | bearish | none
    atr: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _swing_points(df: pd.DataFrame, left: int = 3, right: int = 3):
    """Find swing highs/lows using a simple fractal rule."""
    h, l = df["high"].values, df["low"].values
    highs, lows = [], []
    for i in range(left, len(df) - right):
        if all(h[i] > h[i - j] for j in range(1, left + 1)) and \
           all(h[i] > h[i + j] for j in range(1, right + 1)):
            highs.append((i, float(h[i])))
        if all(l[i] < l[i - j] for j in range(1, left + 1)) and \
           all(l[i] < l[i + j] for j in range(1, right + 1)):
            lows.append((i, float(l[i])))
    return highs, lows


def _classify_trend(highs, lows) -> tuple[str, str]:
    if len(highs) < 2 or len(lows) < 2:
        return "ranging", "Not enough swing points to classify structure."
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    lh = highs[-1][1] < highs[-2][1]
    ll = lows[-1][1] < lows[-2][1]
    if hh and hl:
        return "bullish", "Higher High and Higher Low — uptrend structure."
    if lh and ll:
        return "bearish", "Lower High and Lower Low — downtrend structure."
    return "ranging", "Mixed swings — no clean trend; price is ranging."


def _psych_levels(price: float) -> list[float]:
    """Nearest round numbers above and below price."""
    if price >= 1000:        # gold, indices
        step = 50.0
    elif price >= 100:       # JPY pairs
        step = 1.0
    else:                    # FX majors
        step = 0.0100
    below = (price // step) * step
    return [round(below, 5), round(below + step, 5)]


def _nearest(levels: list[float], price: float, side: str, n: int = 3) -> list[float]:
    if side == "below":
        cands = sorted([x for x in levels if x < price], reverse=True)
    else:
        cands = sorted([x for x in levels if x > price])
    # de-dupe near-identical levels
    out: list[float] = []
    for x in cands:
        if not any(abs(x - y) / price < 0.0005 for y in out):
            out.append(round(x, 5))
        if len(out) >= n:
            break
    return out


def _detect_divergence(df: pd.DataFrame, lows, highs) -> str:
    """Basic RSI divergence on the last two swings."""
    rsi = df["rsi"].values
    if len(lows) >= 2:
        (i1, p1), (i2, p2) = lows[-2], lows[-1]
        if p2 < p1 and rsi[i2] > rsi[i1]:
            return "bullish"   # price lower low, RSI higher low
    if len(highs) >= 2:
        (i1, p1), (i2, p2) = highs[-2], highs[-1]
        if p2 > p1 and rsi[i2] < rsi[i1]:
            return "bearish"   # price higher high, RSI lower high
    return "none"


def build_snapshot(symbol: str, df: pd.DataFrame, timeframe: str = "5min") -> MarketSnapshot | None:
    if df is None or len(df) < 60:
        return None

    df = df.copy()
    df["ema9"]  = ta.ema(df["close"], length=9)
    df["ema21"] = ta.ema(df["close"], length=21)
    df["ema50"] = ta.ema(df["close"], length=50)
    df["rsi"]   = ta.rsi(df["close"], length=14)
    df["atr"]   = ta.atr(df["high"], df["low"], df["close"], length=14)
    df = df.dropna(subset=["ema9", "ema21", "ema50", "rsi", "atr"]).reset_index(drop=True)
    if len(df) < 10:
        return None

    last = df.iloc[-1]
    price = float(last["close"])

    highs, lows = _swing_points(df)
    trend, structure = _classify_trend(highs, lows)

    support = _nearest([p for _, p in lows], price, "below")
    resistance = _nearest([p for _, p in highs], price, "above")
    psych = _psych_levels(price)

    rsi = float(last["rsi"])
    rsi_state = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"

    e9, e21, e50 = last["ema9"], last["ema21"], last["ema50"]
    if e9 > e21 > e50:
        ema_align = "Bullish stack (EMA9 > EMA21 > EMA50), price above all."
    elif e9 < e21 < e50:
        ema_align = "Bearish stack (EMA9 < EMA21 < EMA50), price below all."
    else:
        ema_align = "EMAs intertwined — no clear alignment."

    divergence = _detect_divergence(df, lows, highs)

    return MarketSnapshot(
        symbol=symbol, timeframe=timeframe, price=round(price, 5),
        trend=trend, structure=structure,
        support=support, resistance=resistance, psychological=psych,
        rsi=round(rsi, 1), rsi_state=rsi_state,
        ema_alignment=ema_align, divergence=divergence,
        atr=round(float(last["atr"]), 5),
    )