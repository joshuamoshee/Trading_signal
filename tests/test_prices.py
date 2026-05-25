from src.data.prices import get_recent_bars

def test_fetch_eurusd():
    df = get_recent_bars("EUR/USD", interval="5min", outputsize=50)
    assert not df.empty, "Twelve Data returned no rows"
    assert "close" in df.columns
    assert len(df) > 0
    print(df.tail())