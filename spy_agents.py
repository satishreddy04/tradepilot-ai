import math
import pandas as pd

def _last(x):
    try:return float(x.iloc[-1])
    except:return 0.0

def build_spy_agents(daily,intraday,news_items=None):
    daily=daily.dropna().copy(); intraday=intraday.dropna().copy()
    if daily.empty or intraday.empty:return {}
    close=daily["Close"]
    e8=close.ewm(span=8,adjust=False).mean();e21=close.ewm(span=21,adjust=False).mean();e50=close.ewm(span=50,adjust=False).mean()
    delta=close.diff();gain=delta.clip(lower=0).rolling(14).mean();loss=(-delta.clip(upper=0)).rolling(14).mean();rs=gain/loss.replace(0,float("nan"));rsi=100-(100/(1+rs))
    ema12=close.ewm(span=12,adjust=False).mean();ema26=close.ewm(span=26,adjust=False).mean();macd=ema12-ema26;signal=macd.ewm(span=9,adjust=False).mean()
    tr=pd.concat([(daily.High-daily.Low),(daily.High-daily.Close.shift()).abs(),(daily.Low-daily.Close.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean()
    p=_last(close); trend=p>_last(e8)>_last(e21)>_last(e50)
    ii=intraday.copy(); tp=(ii.High+ii.Low+ii.Close)/3;vwap=_last((tp*ii.Volume).cumsum()/ii.Volume.cumsum().replace(0,float("nan")))
    above=p>vwap; rsi_v=_last(rsi); macd_bull=_last(macd)>_last(signal)
    tech_score=(35 if trend else 0)+(25 if above else 0)+(20 if 50<=rsi_v<=70 else 10 if rsi_v>50 else 0)+(20 if macd_bull else 0)
    atr_pct=(_last(atr)/p*100) if p else 0
    regime="BULL TREND" if trend else ("MIXED / RANGE" if p>_last(e21) else "BEAR / WEAK")
    news_items=news_items or []
    # News/social remain evidence-only until dedicated feeds/LLM credentials are configured.
    news_score=None; social_score=None
    bull=[];bear=[]
    if trend:bull.append("Daily EMA 8 > 21 > 50 with price above EMA8")
    else:bear.append("Daily EMA trend is not fully bullish")
    if above:bull.append("Price above intraday VWAP")
    else:bear.append("Price below intraday VWAP")
    if macd_bull:bull.append("MACD above signal")
    else:bear.append("MACD below signal")
    if rsi_v>=70:bear.append("RSI is extended")
    risk_block=atr_pct>=3.0
    direction="WAIT"
    if not risk_block and tech_score>=75: direction="CALL BIAS"
    elif not risk_block and tech_score<=30: direction="PUT BIAS"
    confidence=tech_score
    state="CONFIRMED" if confidence>=80 and not risk_block else ("READY" if confidence>=65 and not risk_block else "WATCH")
    return {"price":round(p,2),"regime":regime,"technical":{"score":int(tech_score),"ema8":round(_last(e8),2),"ema21":round(_last(e21),2),"ema50":round(_last(e50),2),"vwap":round(vwap,2),"rsi":round(rsi_v,1),"macd_bullish":macd_bull,"atr":round(_last(atr),2),"atr_pct":round(atr_pct,2)},"news":{"score":news_score,"items":len(news_items),"status":"FEED ONLY — LLM sentiment not configured"},"social":{"score":social_score,"status":"NOT CONFIGURED — no social score is fabricated"},"bull_case":bull,"bear_case":bear,"risk":{"blocked":risk_block,"reason":"ATR >= 3% of SPY price" if risk_block else "No volatility block","max_planned_risk":15},"decision":{"direction":direction,"confidence":int(confidence),"state":state,"paper_only":True}}
