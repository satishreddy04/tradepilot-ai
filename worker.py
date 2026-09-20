"""TradePilot scanner worker.

Run this independently of the Streamlit UI. V1 uses a curated liquid universe.
It writes the latest scan to latest_scan.csv. Schedule it every five minutes
with your cloud host/cron while the U.S. market is open.
"""
import time
import pandas as pd
from tradepilot.market import bars, indicators
from tradepilot.alerts import send_telegram

UNIVERSE="SPY QQQ NVDA AMD PLTR ANET AVGO ARM SMCI CRWD NET MU TSLA META AMZN GOOGL APP HOOD COIN RKLB VRT DELL MRVL CLS ALAB TGTX BE".split()

def scan_once():
    raw=bars(UNIVERSE,"5Min",5)
    if raw.empty:
        print("No market data. Configure Alpaca paper credentials.")
        return
    rows=[]
    for symbol,g in raw.groupby("symbol"):
        z=indicators(g)
        if len(z)<50: continue
        r=z.iloc[-1]
        trend=bool(r.close>r.ema8>r.ema21>r.ema50)
        score=(40 if trend else 0)+(30 if r.rvol>=1.5 else 0)+(15 if r.close>3 else 0)+(15 if r.volume>=500000 else 0)
        status="CONFIRMED" if trend and r.rvol>=1.5 else ("READY" if trend else "WATCH")
        rows.append({"Ticker":symbol,"Price":round(r.close,2),"Score":score,"RVOL":round(r.rvol,2) if pd.notna(r.rvol) else None,"Status":status})
    out=pd.DataFrame(rows).sort_values(["Score","RVOL"],ascending=False).head(25)
    out.to_csv("latest_scan.csv",index=False)
    confirmed=out[out.Status=="CONFIRMED"]
    if len(confirmed):
        send_telegram("TradePilot confirmed setups: "+", ".join(confirmed.Ticker.tolist()))
    print(out.to_string(index=False))

if __name__=="__main__":
    scan_once()
