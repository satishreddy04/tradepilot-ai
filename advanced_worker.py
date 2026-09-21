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
    for x in sorted(rows,key=lambda z:(z.get("score",0),z.get("rvol") or 0),reverse=True):
        t=x.get("ticker")
        if t and t not in symbols: symbols.append(t)
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
    quality=sorted(quality,key=lambda z:(z.get("session_score",0),z.get("rvol") or 0),reverse=True)[:20]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"source_snapshot":snap.get("generated_at"),"quality":quality,"status":"OK"},separators=(",",":")))
    print("ADV done",len(quality),flush=True)

if __name__=="__main__": main()
