import json
from pathlib import Path
import pandas as pd
import yfinance as yf

UNIVERSE="NVDA AMD PLTR ANET AVGO ARM SMCI CRWD NET MU TSLA META AMZN GOOGL APP HOOD COIN RKLB VRT DELL MRVL CLS ALAB TGTX BE".split()
OUT=Path("docs/data/backtest.json")
RISK=5.0
START_EQUITY=1500.0

def test_symbol(t):
    # 60 days of 15m data keeps the test reproducible with Yahoo's intraday limits.
    g=yf.download(t,period="60d",interval="15m",auto_adjust=False,progress=False,prepost=False)
    if g.empty:return []
    if isinstance(g.columns,pd.MultiIndex):g.columns=g.columns.get_level_values(0)
    idx=pd.to_datetime(g.index)
    if idx.tz is None:idx=idx.tz_localize("UTC")
    g.index=idx.tz_convert("America/New_York")
    g=g.between_time("09:30","15:59")
    trades=[]
    for day,x in g.groupby(g.index.date):
        if len(x)<8:continue
        x=x.copy()
        # First 15m candle is the ORB on 15m data.
        orb_h=float(x.iloc[0].High);orb_l=float(x.iloc[0].Low)
        x["vwap"]=(x.Close*x.Volume).cumsum()/x.Volume.cumsum().replace(0,float("nan"))
        x["e8"]=x.Close.ewm(span=8,adjust=False).mean();x["e21"]=x.Close.ewm(span=21,adjust=False).mean()
        # Conservative proxy: breakout after ORB, above VWAP and EMA trend.
        entry_i=None
        for j in range(1,len(x)):
            r=x.iloc[j]
            if r.Close>orb_h and r.Close>r.vwap and r.Close>r.e8>r.e21:
                entry_i=j;break
        if entry_i is None:continue
        entry=orb_h;stop=min(entry-.01,max(orb_l,float(x.iloc[entry_i].vwap)))
        risk_share=entry-stop
        if risk_share<=0:continue
        shares=int(RISK/risk_share)
        if shares<1:continue
        t1=entry+1.5*risk_share;t2=entry+2.5*risk_share
        exit_px=float(x.iloc[-1].Close);reason="CLOSE"
        # Assume stop first if stop and target coexist in one candle: deliberately conservative.
        for j in range(entry_i+1,len(x)):
            r=x.iloc[j]
            if r.Low<=stop:exit_px=stop;reason="STOP";break
            if r.High>=t2:exit_px=t2;reason="T2";break
            if r.High>=t1:exit_px=t1;reason="T1";break
        pnl=(exit_px-entry)*shares
        trades.append({"date":str(day),"ticker":t,"entry":round(entry,2),"stop":round(stop,2),"exit":round(exit_px,2),"reason":reason,"shares":shares,"pnl":round(pnl,2)})
    return trades

def main():
    trades=[]
    for t in UNIVERSE:
        try:trades+=test_symbol(t)
        except Exception as e:print(t,e)
    trades.sort(key=lambda z:(z["date"],z["ticker"]))
    equity=START_EQUITY;peak=equity;max_dd=0
    for x in trades:
        equity+=x["pnl"];peak=max(peak,equity);max_dd=max(max_dd,peak-equity);x["equity"]=round(equity,2)
    wins=sum(x["pnl"]>0 for x in trades);losses=sum(x["pnl"]<0 for x in trades)
    gross_win=sum(max(0,x["pnl"]) for x in trades);gross_loss=-sum(min(0,x["pnl"]) for x in trades)
    summary={"starting_equity":START_EQUITY,"ending_equity":round(equity,2),"net_pnl":round(equity-START_EQUITY,2),"trades":len(trades),"wins":wins,"losses":losses,"win_rate":round(100*wins/len(trades),1) if trades else 0,"profit_factor":round(gross_win/gross_loss,2) if gross_loss else None,"max_drawdown_dollars":round(max_dd,2),"risk_per_trade":RISK,"note":"Research estimate using Yahoo 15m bars; excludes slippage, fees, taxes and exact historical time-matched RVOL. Not a profit forecast."}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({"summary":summary,"trades":trades},separators=(",",":")))
    print(summary)
if __name__=="__main__":main()
