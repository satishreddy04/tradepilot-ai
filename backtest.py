import json
from pathlib import Path
import pandas as pd
import yfinance as yf

UNIVERSE="NVDA AMD PLTR ANET AVGO ARM SMCI CRWD NET MU TSLA META AMZN GOOGL APP HOOD COIN RKLB VRT DELL MRVL CLS ALAB TGTX BE".split()
OUT=Path("docs/data/backtest.json")
START_EQUITY=1500.0
RISK_PCT=0.01
MAX_DAILY_LOSS_PCT=0.02
MAX_POSITIONS_PER_DAY=2
MIN_STOP_PCT=0.003
SLIPPAGE_PCT=0.0005

def test_symbol(t):
    g=yf.download(t,period="60d",interval="15m",auto_adjust=False,progress=False,prepost=False)
    if g.empty:return []
    if isinstance(g.columns,pd.MultiIndex):g.columns=g.columns.get_level_values(0)
    idx=pd.to_datetime(g.index)
    if idx.tz is None:idx=idx.tz_localize("UTC")
    g.index=idx.tz_convert("America/New_York")
    g=g.between_time("09:30","15:59")
    signals=[]
    for day,x in g.groupby(g.index.date):
        if len(x)<8:continue
        x=x.copy()
        orb_h=float(x.iloc[0].High);orb_l=float(x.iloc[0].Low)
        typical=(x.High+x.Low+x.Close)/3
        x["vwap"]=(typical*x.Volume).cumsum()/x.Volume.cumsum().replace(0,float("nan"))
        x["e8"]=x.Close.ewm(span=8,adjust=False).mean();x["e21"]=x.Close.ewm(span=21,adjust=False).mean()
        entry_i=None
        for j in range(1,len(x)):
            r=x.iloc[j]
            if r.Close>orb_h and r.Close>r.vwap and r.Close>r.e8>r.e21:
                entry_i=j;break
        if entry_i is None:continue
        raw_entry=orb_h
        structural=max(orb_l,float(x.iloc[entry_i].vwap))
        min_risk=raw_entry*MIN_STOP_PCT
        stop=min(raw_entry-min_risk,structural)
        risk_share=raw_entry-stop
        if risk_share<=0:continue
        signals.append({"date":str(day),"ticker":t,"time":str(x.index[entry_i]),"entry_i":entry_i,
                        "entry_raw":raw_entry,"stop_raw":stop,"risk_share_raw":risk_share,
                        "bars":[{"high":float(r.High),"low":float(r.Low),"close":float(r.Close)} for _,r in x.iloc[entry_i+1:].iterrows()],
                        "close":float(x.iloc[-1].Close)})
    return signals

def main():
    signals=[]
    for t in UNIVERSE:
        try:signals+=test_symbol(t)
        except Exception as e:print(t,e)
    signals.sort(key=lambda z:(z["date"],z["time"],z["ticker"]))
    equity=START_EQUITY;peak=equity;max_dd=0;trades=[];current_day=None;day_pnl=0;day_count=0
    for s in signals:
        if s["date"]!=current_day:
            current_day=s["date"];day_pnl=0;day_count=0
        max_daily_loss=equity*MAX_DAILY_LOSS_PCT
        if day_count>=MAX_POSITIONS_PER_DAY or day_pnl<=-max_daily_loss:continue
        risk_budget=equity*RISK_PCT
        entry=s["entry_raw"]*(1+SLIPPAGE_PCT)
        stop=s["stop_raw"]
        risk_share=entry-stop
        if risk_share<=0:continue
        by_risk=int(risk_budget/risk_share)
        by_cash=int(equity/entry)
        shares=min(by_risk,by_cash)
        if shares<1:continue
        t1=entry+1.5*risk_share;t2=entry+2.5*risk_share
        exit_px=s["close"]*(1-SLIPPAGE_PCT);reason="CLOSE"
        for b in s["bars"]:
            if b["low"]<=stop:
                exit_px=stop*(1-SLIPPAGE_PCT);reason="STOP";break
            if b["high"]>=t2:
                exit_px=t2*(1-SLIPPAGE_PCT);reason="T2";break
            if b["high"]>=t1:
                exit_px=t1*(1-SLIPPAGE_PCT);reason="T1";break
        pnl=(exit_px-entry)*shares
        equity+=pnl;day_pnl+=pnl;day_count+=1
        peak=max(peak,equity);max_dd=max(max_dd,peak-equity)
        trades.append({"date":s["date"],"ticker":s["ticker"],"entry":round(entry,2),"stop":round(stop,2),
                       "exit":round(exit_px,2),"reason":reason,"shares":shares,"position_value":round(entry*shares,2),
                       "risk_budget":round(risk_budget,2),"pnl":round(pnl,2),"equity":round(equity,2)})
    wins=sum(x["pnl"]>0 for x in trades);losses=sum(x["pnl"]<0 for x in trades)
    gw=sum(max(0,x["pnl"]) for x in trades);gl=-sum(min(0,x["pnl"]) for x in trades)
    summary={"starting_equity":START_EQUITY,"ending_equity":round(equity,2),"net_pnl":round(equity-START_EQUITY,2),
      "return_pct":round((equity/START_EQUITY-1)*100,2),"trades":len(trades),"wins":wins,"losses":losses,
      "win_rate":round(100*wins/len(trades),1) if trades else 0,"profit_factor":round(gw/gl,2) if gl else None,
      "max_drawdown_dollars":round(max_dd,2),"risk_pct":RISK_PCT*100,"max_daily_loss_pct":MAX_DAILY_LOSS_PCT*100,
      "max_positions_per_day":MAX_POSITIONS_PER_DAY,"min_stop_pct":MIN_STOP_PCT*100,"slippage_pct":SLIPPAGE_PCT*100,
      "note":"Research simulation using Yahoo 15m bars. Enforces cash buying power, 1% risk sizing, 2% daily loss guard, max 2 trades/day, 0.3% minimum stop and 0.05% entry/exit slippage. Excludes fees, taxes and exact historical time-matched RVOL. Not a profit forecast."}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({"summary":summary,"trades":trades},separators=(",",":")))
    print(summary)
if __name__=="__main__":main()
