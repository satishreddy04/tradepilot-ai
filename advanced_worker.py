import json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import yfinance as yf
from worker import quality_setup,regime

SNAP=Path("docs/data/snapshot.json")
OUT=Path("docs/data/advanced.json")

def main():
    snap=json.loads(SNAP.read_text()) if SNAP.exists() else {}
    rows=snap.get("day",[])
    symbols=[]
    # Advanced Day Trader must analyze the same candidates shown in Day Trades.
    # Preserve snapshot order/status instead of silently replacing the candidate set.
    for row in rows:
        t=row.get("ticker")
        if t and t not in symbols:
            symbols.append(t)
        if len(symbols)>=20: break
    if not symbols:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"quality":[],"status":"NO_CORE_CANDIDATES"}))
        return
    syms=["SPY","QQQ"]+symbols
    print("ADV download",len(syms),flush=True)
    x=yf.download(syms,period="2d",interval="5m",group_by="ticker",auto_adjust=False,actions=False,prepost=True,threads=False,progress=False,timeout=8)
    d=yf.download(["SPY","QQQ"],period="3mo",interval="1d",group_by="ticker",auto_adjust=False,actions=False,threads=False,progress=False,timeout=8)
    m=regime(d)
    quality=[]
    for t in symbols:
        try:
            q=quality_setup(t,x[t],x["SPY"],m)
            if q: quality.append(q)
        except Exception as e: print("ADV",t,repr(e),flush=True)
    # Keep every core Day Trades candidate visible in Advanced, even when the
    # advanced confirmation layer says WAIT/TOO LATE. This prevents a ticker
    # (for example AMAT) from disappearing between tabs.
    by_ticker={q.get("ticker"):q for q in quality}
    ordered=[]
    for row in rows:
        t=row.get("ticker")
        q=by_ticker.get(t)
        if not q: continue
        q["core_status"]=row.get("status")
        q["core_score"]=row.get("score")
        ordered.append(q)
    quality=ordered[:20]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"source_snapshot":snap.get("generated_at"),"quality":quality,"status":"OK"},separators=(",",":")))
    print("ADV done",len(quality),flush=True)

if __name__=="__main__": main()
