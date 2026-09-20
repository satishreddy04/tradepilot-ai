import math
import pandas as pd

def _last(x):
    try:return float(x.iloc[-1])
    except:return 0.0


POSITIVE=("beat","beats","gain","gains","rally","rises","growth","strong","record","upgrade","optimism","bullish","surge","cut rates","rate cut")
NEGATIVE=("miss","misses","loss","losses","falls","drop","weak","downgrade","fear","bearish","selloff","inflation","recession","war","tariff")

def _headline_sentiment(items):
    vals=[]; evidence=[]
    for x in items or []:
        title=str(x.get("title","")).lower()
        pos=sum(w in title for w in POSITIVE); neg=sum(w in title for w in NEGATIVE)
        if pos or neg:
            score=(pos-neg)/max(1,pos+neg);vals.append(score);evidence.append(x.get("title",""))
    if not vals:return None,[]
    return round(50+50*sum(vals)/len(vals)),evidence[:5]

def _llm_sentiment(news_items,social_items):
    key=os.getenv("OPENAI_API_KEY")
    if not key:return None
    payload={"model":os.getenv("OPENAI_MODEL","gpt-5-mini"),"input":[{"role":"system","content":"Analyze supplied SPY market news/social evidence only. Return JSON with news_score and social_score from 0 bearish to 100 bullish, plus short news_summary and social_summary. Do not invent facts."},{"role":"user","content":json.dumps({"news":news_items[:12],"social":social_items[:20]})}],"text":{"format":{"type":"json_object"}}}
    try:
        r=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},json=payload,timeout=30);r.raise_for_status();z=r.json()
        txt=z.get("output_text")
        if not txt:
            txt=z["output"][0]["content"][0]["text"]
        return json.loads(txt)
    except Exception as e:
        print("llm sentiment",e);return None
\ndef build_spy_agents(daily,intraday,news_items=None,social_items=None):
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
    available=[tech_score]+([news_score] if news_score is not None else [])+([social_score] if social_score is not None else [])\n    confidence=round(sum(available)/len(available))
    state="CONFIRMED" if confidence>=80 and not risk_block else ("READY" if confidence>=65 and not risk_block else "WATCH")
    return {"price":round(p,2),"regime":regime,"technical":{"score":int(tech_score),"ema8":round(_last(e8),2),"ema21":round(_last(e21),2),"ema50":round(_last(e50),2),"vwap":round(vwap,2),"rsi":round(rsi_v,1),"macd_bullish":macd_bull,"atr":round(_last(atr),2),"atr_pct":round(atr_pct,2)},"news":{"score":news_score,"items":len(news_items),"status":"LLM + headline evidence" if llm else "Headline evidence score","summary":llm.get("news_summary") if llm else None,"evidence":news_evidence},"social":{"score":social_score,"items":len(social_items),"status":"LLM + social evidence" if llm and social_items else ("Evidence score" if social_items else "Awaiting authorized social feed"),"summary":llm.get("social_summary") if llm else None,"evidence":social_evidence},"bull_case":bull,"bear_case":bear,"risk":{"blocked":risk_block,"reason":"ATR >= 3% of SPY price" if risk_block else "No volatility block","max_planned_risk":15},"decision":{"direction":direction,"confidence":int(confidence),"state":state,"paper_only":True}}
