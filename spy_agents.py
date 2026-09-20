import math,os,json,requests
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


def build_options_agent(spot,direction,max_risk=15):
    out={"status":"WAIT","direction":direction,"contracts_checked":0,"candidate":None,"source":"Yahoo/yfinance option chain; verify with broker"}
    if direction not in ("CALL BIAS","PUT BIAS"):return out
    try:
        import yfinance as yf
        t=yf.Ticker("SPY"); expiries=list(t.options or [])
        if not expiries:return out
        from datetime import date,datetime
        choices=[]
        for exp in expiries:
            try:
                dte=(datetime.strptime(exp,"%Y-%m-%d").date()-date.today()).days
                if 7<=dte<=30:choices.append((dte,exp))
            except:pass
        if not choices:return out
        dte,exp=min(choices)
        ch=t.option_chain(exp); df=ch.calls.copy() if direction=="CALL BIAS" else ch.puts.copy()
        out["contracts_checked"]=len(df)
        if df.empty:return out
        df=df.copy();df["mid"]=(df["bid"].fillna(0)+df["ask"].fillna(0))/2
        df["spread_pct"]=(df["ask"]-df["bid"])/df["mid"].replace(0,float("nan"))*100
        df["distance"]=(df["strike"]-spot).abs()/spot*100
        liquid=df[(df["bid"]>0)&(df["ask"]>0)&(df["mid"]>0)&(df["spread_pct"]<=12)&(df["distance"]<=3)]
        if "openInterest" in liquid: liquid=liquid[liquid["openInterest"].fillna(0)>=100]
        if "volume" in liquid: liquid=liquid[liquid["volume"].fillna(0)>=10]
        if liquid.empty:
            out["status"]="NO TRADE";out["reason"]="No sufficiently liquid near-the-money contract passed spread/volume/OI filters";return out
        liquid["cost"]=liquid["ask"]*100
        affordable=liquid[liquid["cost"]<=max_risk]
        pool=affordable if not affordable.empty else liquid
        row=pool.sort_values(["distance","spread_pct"]).iloc[0]
        cost=float(row["cost"])
        if cost>max_risk:
            long_strike=float(row["strike"])
            shorts=liquid[(liquid["strike"]>long_strike)&(liquid["strike"]<=long_strike+5)] if direction=="CALL BIAS" else liquid[(liquid["strike"]<long_strike)&(liquid["strike"]>=long_strike-5)]
            best=None
            for _,sr in shorts.iterrows():
                debit=max(0.0,(float(row["ask"])-float(sr["bid"]))*100); width=abs(float(sr["strike"])-long_strike)*100
                if 0<debit<width and debit<=max_risk:
                    slip=abs(debit-max(0.0,(float(row["mid"])-float(sr["mid"]))*100))
                    if best is None or slip<best[0]: best=(slip,debit,width,sr)
            if best is None:
                out["status"]="NO TRADE";out["reason"]="Single option exceeds risk budget and no liquid debit spread fits the planned-risk limit";return out
            _,debit,width,sr=best
            out["status"]="SPREAD CANDIDATE";out["spread"]={"expiration":exp,"dte":dte,"type":"CALL DEBIT SPREAD" if direction=="CALL BIAS" else "PUT DEBIT SPREAD","buy_strike":round(long_strike,2),"sell_strike":round(float(sr["strike"]),2),"estimated_debit":round(debit,2),"max_loss":round(debit,2),"max_profit":round(width-debit,2),"width":round(width,2)}
            return out
        out["status"]="CANDIDATE"
        out["candidate"]={"expiration":exp,"dte":dte,"type":"CALL" if direction=="CALL BIAS" else "PUT","strike":round(float(row["strike"]),2),"bid":round(float(row["bid"]),2),"ask":round(float(row["ask"]),2),"mid":round(float(row["mid"]),2),"spread_pct":round(float(row["spread_pct"]),1),"volume":int(row.get("volume",0) or 0),"open_interest":int(row.get("openInterest",0) or 0),"iv_pct":round(float(row.get("impliedVolatility",0) or 0)*100,1),"max_debit":round(cost,2)}
        return out
    except Exception as e:
        out["status"]="UNAVAILABLE";out["reason"]=str(e)[:160];return out

def build_spy_agents(daily,intraday,news_items=None,social_items=None):
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
    news_items=news_items or []; social_items=social_items or []
    news_score,news_evidence=_headline_sentiment(news_items)
    social_score,social_evidence=_headline_sentiment(social_items)
    llm=_llm_sentiment(news_items,social_items)
    if llm:
        news_score=llm.get("news_score",news_score); social_score=llm.get("social_score",social_score)
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
    available=[tech_score]+([news_score] if news_score is not None else [])+([social_score] if social_score is not None else [])
    confidence=round(sum(available)/len(available))
    state="CONFIRMED" if confidence>=80 and not risk_block else ("READY" if confidence>=65 and not risk_block else "WATCH")
    return {"price":round(p,2),"regime":regime,"technical":{"score":int(tech_score),"ema8":round(_last(e8),2),"ema21":round(_last(e21),2),"ema50":round(_last(e50),2),"vwap":round(vwap,2),"rsi":round(rsi_v,1),"macd_bullish":macd_bull,"atr":round(_last(atr),2),"atr_pct":round(atr_pct,2)},"news":{"score":news_score,"items":len(news_items),"status":"LLM + headline evidence" if llm else "Headline evidence score","summary":llm.get("news_summary") if llm else None,"evidence":news_evidence},"social":{"score":social_score,"items":len(social_items),"status":"LLM + social evidence" if llm and social_items else ("Evidence score" if social_items else "Awaiting authorized social feed"),"summary":llm.get("social_summary") if llm else None,"evidence":social_evidence},"bull_case":bull,"bear_case":bear,"risk":{"blocked":risk_block,"reason":"ATR >= 3% of SPY price" if risk_block else "No volatility block","max_planned_risk":15},"decision":{"direction":direction,"confidence":int(confidence),"state":state,"paper_only":True},"options":build_options_agent(p,direction,15)}
