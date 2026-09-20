from datetime import datetime, timedelta, timezone
import pandas as pd
from .config import settings

def _stock_client():
    if not settings.alpaca_key or not settings.alpaca_secret:
        return None
    from alpaca.data.historical import StockHistoricalDataClient
    return StockHistoricalDataClient(settings.alpaca_key, settings.alpaca_secret)

def bars(symbols, timeframe="5Min", days=5):
    c=_stock_client()
    if c is None:
        return pd.DataFrame()
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    tf = TimeFrame(5, TimeFrameUnit.Minute) if timeframe=="5Min" else TimeFrame.Day
    req=StockBarsRequest(symbol_or_symbols=symbols,timeframe=tf,start=datetime.now(timezone.utc)-timedelta(days=days))
    return c.get_stock_bars(req).df.reset_index()

def indicators(g: pd.DataFrame):
    g=g.sort_values("timestamp").copy()
    for n in (8,21,50):
        g["ema"+str(n)]=g.close.ewm(span=n,adjust=False).mean()
    g["avgvol20"]=g.volume.rolling(20).mean()
    g["rvol"]=g.volume/g.avgvol20
    return g
