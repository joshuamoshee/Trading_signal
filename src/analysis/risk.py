def pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s:
        return 0.1     # broker conventions vary for gold — confirm yours
    return 0.0001


def stop_distance_pips(symbol: str, entry: float, stop: float) -> float:
    return round(abs(entry - stop) / pip_size(symbol), 1)