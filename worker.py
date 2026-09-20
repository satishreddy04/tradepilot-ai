import json,os
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import yfinance as yf
import requests
from spy_agents import build_spy_agents

UNIVERSE_FILE=Path("universe.txt")

def load_universe():
    symbols=[]
    try:
        for url in ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt","https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"):
            x=pd.read_csv(url,sep="|")
            col="Symbol" if "Symbol" in x.columns else "ACT Symbol"
            symbols.extend(x[col].dropna().astype(str).tolist())
        symbols=[s.strip().upper().replace(".","-") for s in symbols]
        symbols=[s for s in dict.fromkeys(symbols) if s and s.isascii() and "^" not in s and "$" not in s and len(s)<=6 and not s.startswith("File Creation")]
        if len(symbols)>=1000:return symbols
    except Exception as e: print("universe discovery",e)
    return [x.strip().upper() for x in UNIVERSE_FILE.read_text().splitlines() if x.strip() and not x.startswith("#")]

def discover_candidates(symbols):
    keep=[]
    for start in range(0,len(symbols),150):
        batch=symbols[start:start+150]
        try: d=yf.download(batch,period="3mo",interval="1d",group_by="ticker",threads=True,progress=False,timeout=25)
        except Exception as e: print("discovery batch",start,e); continue
        for t in batch:
            try:
                g=(d[t] if len(batch)>1 else d).dropna()
                if len(g)<50: continue
                close=g.Close; vol=g.Volume; p=float(close.iloc[-1]); av=float(vol.tail(20).mean()); dollar=p*av
                e8=float(close.ewm(span=8,adjust=False).mean().iloc[-1]); e21=float(close.ewm(span=21,adjust=False).mean().iloc[-1]); e50=float(close.ewm(span=50,adjust=False).mean().iloc[-1])
                adr=float((((g.High-g.Low)/close)*100).tail(20).mean()); momentum=(p/e21-1) if e21 else 0
                if p>=3 and av>=500000 and dollar>=15000000 and adr>=2 and p>e8>e21>e50: keep.append((t,momentum,adr,dollar))
            except Exception: pass
    keep.sort(key=lambda z:(z[1],z[2],z[3]),reverse=True)
    return [x[0] for x in keep[:100]]

U=[]
OUT=Path("docs/data/snapshot.json")
STATE=Path("docs/data/state.json")
JOURNAL=Path("docs/data/journal.json")

def num(x):
    try:return None if pd.isna(x) else round(float(x),2)
    except:return None

def ind(g):
    g=g.copy().dropna()
    g["e8"]=g.Close.ewm(span=8,adjust=False).mean()
    g["e21"]=g.Close.ewm(span=21,adjust=False).mean()
    g["e50"]=g.Close.ewm(span=50,adjust=False).mean()
    return g

def regular_session(g):
    """Keep only NYSE/Nasdaq regular-session 5m bars (09:30-16:00 ET)."""
    g=g.copy().dropna()
    idx=pd.to_datetime(g.index)
    if idx.tz is None:
        idx=idx.tz_localize("UTC")
    idx=idx.tz_convert("America/New_York")
    g.index=idx
    return g.between_time("09:30","15:59",inclusive="both")

def add_intraday_rvol(g):
    """RVOL versus the same 5-minute slot on prior sessions, not a rolling 20-bar average."""
    g=regular_session(g)
    if g.empty:return g
    slots=g.index.strftime("%H:%M")
    dates=pd.Series(g.index.date,index=g.index)
    out=[]
    for pos,(ts,row) in enumerate(g.iterrows()):
        slot=slots[pos]; day=dates.iloc[pos]
        prior=g[(g.index.date < day) & (g.index.strftime("%H:%M")==slot)].Volume.tail(4)
        base=float(prior.mean()) if len(prior) else float("nan")
        out.append(float(row.Volume)/base if base>0 else float("nan"))
    g["rv"]=out
    return g

def day_setup(t,g):
    g=add_intraday_rvol(g)
    if len(g)<20:return
    latest_day=g.index[-1].date()
    today=g[g.index.date==latest_day]
    if len(today)<3:return
    r=today.iloc[-1]; p=float(r.Close)
    today["e8"]=today.Close.ewm(span=8,adjust=False).mean()
    today["e21"]=today.Close.ewm(span=21,adjust=False).mean()
    r=today.iloc[-1]
    trend=bool(p>r.e8>r.e21)
    orb=today.iloc[:3]
    orb_high=float(orb.High.max()); orb_low=float(orb.Low.min())
    cum_pv=(today.Close*today.Volume).cumsum(); cum_v=today.Volume.cumsum()
    vwap=float((cum_pv/cum_v.replace(0,float("nan"))).iloc[-1])
    rv=float(r.rv) if pd.notna(r.rv) else None
    vol_ok=rv is not None and rv>=1.5
    above_vwap=p>vwap
    confirmed=len(today)>3 and p>orb_high and trend and above_vwap and vol_ok
    near=p>=orb_high*.995
    ready=trend and above_vwap and near
    status="CONFIRMED" if confirmed else ("READY" if ready else "WATCH")
    score=(25 if trend else 0)+(20 if above_vwap else 0)+(25 if vol_ok else 12 if rv is not None and rv>=1 else 0)+(30 if p>orb_high else 15 if near else 0)
    entry=orb_high
    structural=max(orb_low,vwap)
    stop=min(entry-.01,structural)
    risk=max(.01,entry-stop)
    chart=[{"time":str(i),"open":num(x.Open),"high":num(x.High),"low":num(x.Low),"close":num(x.Close)} for i,x in today.tail(50).iterrows()]
    return {"ticker":t,"price":num(p),"score":min(100,int(score)),"rvol":num(rv),"setup":"15m ORB + VWAP + RVOL","status":status,"entry":num(entry),"stop":num(stop),"t1":num(entry+1.5*risk),"t2":num(entry+2.5*risk),"risk_share":num(risk),"vwap":num(vwap),"orb_high":num(orb_high),"orb_low":num(orb_low),"chart":chart}


def quality_setup(t,g,spy_g,market):
    """Research-only A+ day-trade quality layer. It does not alter the existing day_setup."""
    base=day_setup(t,g)
    if not base:return
    x=add_intraday_rvol(g); sx=regular_session(spy_g)
    latest=x.index[-1].date(); today=x[x.index.date==latest]
    if len(today)<4:return
    r=today.iloc[-1]; p=float(r.Close)
    today["e8"]=today.Close.ewm(span=8,adjust=False).mean();today["e21"]=today.Close.ewm(span=21,adjust=False).mean()
    tp=(today.High+today.Low+today.Close)/3; vw=(tp*today.Volume).cumsum()/today.Volume.cumsum().replace(0,float("nan"))
    vwap=float(vw.iloc[-1]); vwap_rising=len(vw)>=4 and float(vw.iloc[-1])>float(vw.iloc[-4])
    ema_rising=len(today)>=4 and float(today.e8.iloc[-1])>float(today.e8.iloc[-4]) and float(today.e21.iloc[-1])>=float(today.e21.iloc[-4])
    orb=today.iloc[:3]; orb_high=float(orb.High.max()); orb_low=float(orb.Low.min())
    close_confirm=len(today)>3 and float(today.Close.iloc[-1])>orb_high
    recent_vol=float(today.Volume.iloc[-4:-1].mean()) if len(today)>=4 else 0
    breakout_volume=recent_vol>0 and float(r.Volume)>recent_vol*1.2
    rv=float(r.rv) if pd.notna(r.rv) else 0.0
    # Time-matched relative strength vs SPY from today's regular-session return.
    st=sx[sx.index.date==sx.index[-1].date()] if len(sx) else sx
    stock_ret=(p/float(today.Close.iloc[0])-1)*100 if len(today) else 0
    spy_ret=(float(st.Close.iloc[-1])/float(st.Close.iloc[0])-1)*100 if len(st)>1 else 0
    rs=stock_ret-spy_ret; rs_ok=rs>=0.30
    market_ok=bool(market.get("spy",{}).get("bullish")) and bool(market.get("qqq",{}).get("bullish"))
    extension=(p/orb_high-1)*100 if orb_high else 0; no_chase=extension<=0.5
    checks={"ORB close":close_confirm,"VWAP":p>vwap,"VWAP rising":vwap_rising,"EMA trend":p>float(r.e8)>float(r.e21),"EMA rising":ema_rising,"RVOL ≥ 2":rv>=2,"Breakout volume":breakout_volume,"Relative strength":rs_ok,"SPY + QQQ aligned":market_ok,"Not extended":no_chase}
    score=round(100*sum(checks.values())/len(checks))
    grade="A+" if score>=90 else ("A" if score>=80 else ("B" if score>=70 else "C"))
    state="A+ CONFIRMED" if grade=="A+" and close_confirm and no_chase else ("CONFIRMED" if score>=80 and close_confirm else ("READY" if score>=70 else "WATCH"))
    entry=float(base["entry"]); stop=float(base["stop"]); risk=max(.01,entry-stop)
    shares=min(int(15/risk),int(1500/entry)) if entry>0 else 0
    # Session-specific context: the same candidate is evaluated differently through the day.
    hhmm=today.index[-1].strftime("%H:%M")
    if hhmm<"09:30": phase="PREMARKET"
    elif hhmm<"10:30": phase="OPENING"
    elif hhmm<"13:30": phase="MIDDAY"
    elif hhmm<"15:45": phase="POWER HOUR"
    else: phase="CLOSE"
    hod=float(today.High.max()); lod=float(today.Low.min())
    last6=today.tail(6)
    range6=float(last6.High.max()-last6.Low.min()) if len(last6) else 0
    avg_range=float((today.High-today.Low).tail(12).mean()) if len(today) else 0
    tight=avg_range>0 and range6<=avg_range*2.5
    vol_contract=len(today)>=8 and float(today.Volume.tail(3).mean())<float(today.Volume.tail(8).mean())
    near_hod=p>=hod*.997 if hod else False
    vwap_reclaim=p>vwap and float(today.Close.iloc[-2])<=float(vw.iloc[-2]) if len(today)>1 else False
    session_checks={
      "PREMARKET":{"Daily trend":bool(market_ok),"Relative strength":rs_ok,"Liquidity / RVOL":rv>=1.5,"Not extended":no_chase},
      "OPENING":checks,
      "MIDDAY":{"Above VWAP":p>vwap,"VWAP rising":vwap_rising,"EMA trend":p>float(r.e8)>float(r.e21),"Tight consolidation":tight,"Volume contraction":vol_contract,"Relative strength":rs_ok,"Market aligned":market_ok,"Not extended":no_chase},
      "POWER HOUR":{"Near HOD":near_hod,"Above VWAP":p>vwap,"EMA trend":p>float(r.e8)>float(r.e21),"Volume expansion":breakout_volume or rv>=1.5,"Relative strength":rs_ok,"Market aligned":market_ok,"Not extended":no_chase},
      "CLOSE":{"Above VWAP":p>vwap,"EMA trend":p>float(r.e8)>float(r.e21),"Relative strength":rs_ok,"Market aligned":market_ok}
    }
    active=session_checks.get(phase,checks); session_score=round(100*sum(active.values())/len(active)) if active else 0
    session_state="A+ CONFIRMED" if session_score>=90 and no_chase else ("CONFIRMED" if session_score>=80 else ("READY" if session_score>=70 else "WATCH"))
    return {**base,"quality_score":score,"grade":grade,"quality_state":state,"phase":phase,"session_score":session_score,"session_state":session_state,"session_checks":active,"relative_strength":round(rs,2),"stock_session_return":round(stock_ret,2),"spy_session_return":round(spy_ret,2),"vwap_rising":vwap_rising,"ema_rising":ema_rising,"breakout_volume":breakout_volume,"market_aligned":market_ok,"extension_pct":round(extension,2),"no_chase":no_chase,"hod":num(hod),"lod":num(lod),"tight_consolidation":tight,"volume_contraction":vol_contract,"vwap_reclaim":vwap_reclaim,"checks":checks,"shares":shares,"planned_risk":round(shares*risk,2),"t1_1r":num(entry+risk),"t2_2r":num(entry+2*risk)}

def swing_setup(t,g):
    g=ind(g)
    if len(g)<21:return
    r=g.iloc[-1];p=float(r.Close);trend=p>r.e8>r.e21;full=trend and r.e21>r.e50
    av=g.Volume.rolling(20).mean();rv=float(r.Volume/av.iloc[-1]) if pd.notna(av.iloc[-1]) and av.iloc[-1]>0 else 0
    ph=float(g.High.shift(1).rolling(20).max().iloc[-1]);lo=float(g.Low.tail(10).min());near=p>=ph*.985
    score=(35 if full else 20 if trend else 0)+(25 if rv>=1.5 else 12 if rv>=1 else 0)+(25 if near else 0)+15
    status="CONFIRMED" if p>ph and rv>=1.5 and trend else ("READY" if trend and near else "WATCH")
    entry=ph;stop=max(lo,entry*.96);risk=max(.01,entry-stop)
    chart=[{"time":str(i),"open":num(x.Open),"high":num(x.High),"low":num(x.Low),"close":num(x.Close)} for i,x in g.tail(50).iterrows()]
    return {"ticker":t,"price":num(p),"score":min(100,int(score)),"rvol":num(rv),"setup":"EMA trend / 20-bar breakout","status":status,"entry":num(entry),"stop":num(stop),"t1":num(entry+2*risk),"t2":num(entry+3*risk),"risk_share":num(risk),"chart":chart}

def regime(d):
    vals={};bull=0
    for t in ["SPY","QQQ"]:
        try:
            g=ind(d[t]);r=g.iloc[-1];ok=bool(r.Close>r.e8>r.e21>r.e50);bull+=int(ok);vals[t.lower()]={"price":num(r.Close),"bullish":ok}
        except:vals[t.lower()]={}
    breadth=[]
    for t in [x for x in U if x not in ("SPY","QQQ")]:
        try:g=ind(d[t]);r=g.iloc[-1];breadth.append(bool(r.Close>r.e21))
        except:pass
    b=round(100*sum(breadth)/len(breadth)) if breadth else 50;score=round(bull/2*60+b*.4)
    label="BULLISH" if score>=65 else ("BEARISH" if score<=35 else "NEUTRAL / MIXED")
    return {"label":label,"score":score,"breadth":b,**vals}

def news():
    out=[]
    for t in ["SPY","QQQ","NVDA","AMD","TSLA","META","AMZN"]:
        try:
            for n in (yf.Ticker(t).news or [])[:2]:
                x=n.get("content",n);title=x.get("title") or n.get("title");link=(x.get("canonicalUrl") or {}).get("url") or n.get("link")
                if title:out.append({"ticker":t,"title":title,"publisher":x.get("provider",{}).get("displayName",n.get("publisher","")),"published":x.get("pubDate",n.get("providerPublishTime","")),"link":link or "#"})
        except:pass
    return out[:20]

def main():
    global U
    broad=load_universe()
    candidates=discover_candidates(broad)
    U=["SPY","QQQ"]+[x for x in candidates if x not in ("SPY","QQQ")]
    print("dynamic discovery:",len(broad),"listed ->",len(candidates),"intraday candidates")
    d=yf.download(U,period="4mo",interval="1d",group_by="ticker",threads=True,progress=False)
    # prepost=False prevents extended-hours prints from contaminating ORB/VWAP/RVOL.
    i=yf.download(U,period="5d",interval="5m",group_by="ticker",prepost=False,threads=True,progress=False)
    day=[];swing=[];quality=[]
    for t in [x for x in U if x not in ("SPY","QQQ")]:
        try:
            x=day_setup(t,i[t])
            if x:day.append(x)
        except Exception as e:print("day",t,e)
        try:
            x=swing_setup(t,d[t])
            if x:swing.append(x)
        except Exception as e:print("swing",t,e)
    day=sorted(day,key=lambda x:(x["score"],x["rvol"] or 0),reverse=True)[:25]
    swing=sorted(swing,key=lambda x:(x["score"],x["rvol"] or 0),reverse=True)[:25]
    m=regime(d)
    news_items=news()
    try:
        spy_daily=d["SPY"].dropna()
        spy_intraday=regular_session(i["SPY"]).dropna()
        spy_ai=build_spy_agents(spy_daily,spy_intraday,[x for x in news_items if x.get("ticker")=="SPY"])
        if spy_ai:
            spy_ai["data_asof"]=str(spy_intraday.index[-1]) if len(spy_intraday) else None
            spy_ai["market_data_status"]="LATEST AVAILABLE SESSION"
    except Exception as e:
        print("spy agents",e); spy_ai={"error":str(e)[:180],"market_data_status":"UNAVAILABLE"}
    snap={"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"spy_ai":spy_ai,"scanner":{"listed_symbols":len(broad),"passed_filters":len(candidates),"intraday_scanned":max(0,len(U)-2),"day_displayed":len(day),"swing_displayed":len(swing),"dynamic":True},"market":m,"day":day,"swing":swing,"quality":quality,"news":news_items,"analytics":{"bullish_count":sum(x["status"]!="WATCH" for x in swing),"bearish_count":sum(x["status"]=="WATCH" for x in swing),"day_confirmed":sum(x["status"]=="CONFIRMED" for x in day),"swing_ready":sum(x["status"] in ("READY","CONFIRMED") for x in swing)}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(snap,separators=(",",":")))
    # Paper journal: open a simulated trade on a new CONFIRMED day signal and track stop/T1/T2.
    try: journal=json.loads(JOURNAL.read_text()) if JOURNAL.exists() else []
    except: journal=[]
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    open_by_ticker={x["ticker"]:x for x in journal if x.get("kind")=="DAY" and x.get("status")=="OPEN"}
    day_map={x["ticker"]:x for x in day}
    for ticker,tr in list(open_by_ticker.items()):
        x=day_map.get(ticker)
        if not x: continue
        price=float(x.get("price") or 0); stop=float(tr["stop"]); t1=float(tr["t1"]); t2=float(tr["t2"])
        if price<=stop: tr.update(status="CLOSED",exit=price,outcome="STOP",closed_at=now,pnl=round((price-tr["entry"])*tr["shares"],2))
        elif price>=t2: tr.update(status="CLOSED",exit=price,outcome="T2",closed_at=now,pnl=round((price-tr["entry"])*tr["shares"],2))
        elif price>=t1 and not tr.get("t1_hit"): tr["t1_hit"]=True; tr["t1_hit_at"]=now
    try: previous_for_journal=json.loads(STATE.read_text()) if STATE.exists() else {}
    except: previous_for_journal={}
    for x in day:
        key="DAY:"+x["ticker"]
        if x["status"]=="CONFIRMED" and previous_for_journal.get(key,"WATCH")!="CONFIRMED" and x["ticker"] not in open_by_ticker:
            entry=float(x.get("price") or x.get("entry") or 0); stop=float(x.get("stop") or 0); risk=max(.01,entry-stop)
            shares=min(int(15/risk),int(1500/entry)) if entry>0 else 0
            if shares>0:
                journal.append({"kind":"DAY","ticker":x["ticker"],"setup":x.get("setup"),"opened_at":now,"entry":round(entry,2),"stop":stop,"t1":float(x["t1"]),"t2":float(x["t2"]),"shares":shares,"planned_risk":round((entry-stop)*shares,2),"status":"OPEN","t1_hit":False,"score":x.get("score"),"rvol":x.get("rvol")})
    JOURNAL.parent.mkdir(parents=True,exist_ok=True)
    JOURNAL.write_text(json.dumps(journal[-500:],separators=(",",":")))

    # Persist setup states so Telegram only fires on meaningful transitions.
    try: previous=json.loads(STATE.read_text()) if STATE.exists() else {}
    except: previous={}
    current={}; transitions=[]
    for kind,rows in (("DAY",day),("SWING",swing)):
        for x in rows:
            key=kind+":"+x["ticker"]; new=x["status"]; old=previous.get(key,"WATCH")
            current[key]=new
            if new in ("READY","CONFIRMED") and new!=old:
                transitions.append((kind,old,new,x))
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(current,separators=(",",":")))

    token=os.getenv("TELEGRAM_BOT_TOKEN"); chat=os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        for kind,old,new,x in transitions[:10]:
            risk=float(x.get("risk_share") or 0); entry=float(x.get("entry") or 0)
            by_risk=int(15/risk) if risk>0 else 0; by_cash=int(1500/entry) if entry>0 else 0
            shares=min(by_risk,by_cash)
            msg=(f"TradePilot {kind}: {old} -> {new}\n{x['ticker']} | {x.get('setup')}\n"
                 f"Entry {x.get('entry')} | Stop {x.get('stop')} | T1 {x.get('t1')} | T2 {x.get('t2')}\n"
                 f"RVOL {x.get('rvol')}x | Score {x.get('score')}/100 | Max shares {shares} | Planned risk <= $15")
            try: requests.post("https://api.telegram.org/bot"+token+"/sendMessage",data={"chat_id":chat,"text":msg},timeout=15)
            except Exception as e: print("telegram",e)
    print("built",m["label"],len(day),len(swing))

if __name__=="__main__":main()
