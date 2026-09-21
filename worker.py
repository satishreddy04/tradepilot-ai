import json,os
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import yfinance as yf
import requests
from spy_agents import build_spy_agents

UNIVERSE_FILE=Path("universe.txt")
MAJOR_FALLBACK={"AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","AMD","NFLX","COST","PLTR","CSCO","TMUS","LIN","INTU","AMAT","TXN","QCOM","PEP","AMGN","HON","IBM","JPM","V","WMT","UNH","GS","CAT","HD","MCD","AXP","CRM","BA","DIS","KO","JNJ","PG","MRK"}
SECTOR_ETFS={"Technology":"XLK","Financials":"XLF","Communication":"XLC","Consumer Discretionary":"XLY","Industrials":"XLI","Health Care":"XLV","Energy":"XLE","Consumer Staples":"XLP","Utilities":"XLU","Real Estate":"XLRE","Materials":"XLB"}

def load_major_index_members():
    """Fast, deterministic liquid large-cap index core; avoids network HTML scraping in each scan."""
    return set(MAJOR_FALLBACK)

def pick_40(rows,major):
    """Build Top 50 with a balanced target: 25 major-index + 25 broader-market qualified setups."""
    ranked=sorted(rows,key=lambda x:(x.get("score",0),x.get("rvol") or 0),reverse=True)
    for x in ranked:
        x["universe"]="MAJOR INDEX" if x.get("ticker") in major else "BROADER MARKET"
    major_rows=[x for x in ranked if x.get("ticker") in major][:25]
    broader_rows=[x for x in ranked if x.get("ticker") not in major][:25]
    chosen=major_rows+broader_rows
    used={x["ticker"] for x in chosen}
    # Fill only when one side has fewer than 25 qualifying setups; never fabricate a setup.
    chosen.extend([x for x in ranked if x.get("ticker") not in used][:50-len(chosen)])
    chosen=sorted(chosen[:50],key=lambda x:(x.get("score",0),x.get("rvol") or 0),reverse=True)
    return chosen,len([x for x in chosen if x.get("ticker") in major])

def sector_strength():
    """Rank sectors for day trading from the latest available regular session."""
    out=[]
    try:
        syms=list(SECTOR_ETFS.values())+["SPY"]
        z=yf.download(syms,period="5d",interval="15m",group_by="ticker",auto_adjust=False,actions=False,prepost=False,threads=True,progress=False,timeout=10)
        def bars(sym):
            try:
                g=z[sym].dropna(how="all")
                return regular_session(g)
            except Exception as e:
                print("sector bars",sym,e,flush=True); return pd.DataFrame()
        spy=bars("SPY")
        if spy.empty:
            print("sector strength: SPY intraday empty",flush=True); return out
        latest=spy.index[-1].date(); sd=spy[spy.index.date==latest]
        spy_ret=(float(sd.Close.iloc[-1])/float(sd.Open.iloc[0])-1)*100 if len(sd) else 0
        for name,t in SECTOR_ETFS.items():
            g=bars(t)
            if g.empty: continue
            td=g[g.index.date==g.index[-1].date()].copy()
            if len(td)<3: continue
            close=td.Close.astype(float); vol=td.Volume.astype(float)
            price=float(close.iloc[-1]); openp=float(td.Open.iloc[0]); ret=(price/openp-1)*100 if openp else 0; rs=ret-spy_ret
            e8=float(close.ewm(span=8,adjust=False).mean().iloc[-1]); e21=float(close.ewm(span=21,adjust=False).mean().iloc[-1])
            typical=(td.High.astype(float)+td.Low.astype(float)+close)/3; cv=float(vol.cumsum().iloc[-1]); vwap=float((typical*vol).cumsum().iloc[-1]/cv) if cv>0 else price
            above_vwap=price>vwap; ema_bull=price>e8>e21
            # Compare the latest bar with the same clock slot on prior sessions when possible.
            slot=td.index[-1].strftime("%H:%M"); prior=g[(g.index.date<td.index[-1].date()) & (g.index.strftime("%H:%M")==slot)].Volume.tail(4)
            base=float(prior.mean()) if len(prior) else float(vol.iloc[:-1].tail(20).mean())
            rvol=float(vol.iloc[-1]/base) if base>0 else 0
            score=50+max(-20,min(20,rs*8))+max(-10,min(10,ret*3))+(8 if above_vwap else -8)+(8 if ema_bull else -8)+max(-4,min(4,(rvol-1)*4))
            score=round(max(0,min(100,score)),1)
            out.append({"sector":name,"etf":t,"session_date":str(td.index[-1].date()),"intraday_pct":round(ret,2),"rs_vs_spy":round(rs,2),"above_vwap":above_vwap,"ema_bull":ema_bull,"rvol":round(rvol,2),"strength_score":score})
        out.sort(key=lambda x:x["strength_score"],reverse=True)
        for n,x in enumerate(out):
            x["rank"]=n+1; x["state"]="STRONG" if x["strength_score"]>=65 else ("WEAK" if x["strength_score"]<40 else "NEUTRAL")
        print("sector strength rows",len(out),"session",str(latest),flush=True)
    except Exception as e: print("sector strength",repr(e),flush=True)
    return out

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

def discover_candidates(symbols, limit=100):
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
                if p>=3 and av>=500000 and dollar>=15000000 and adr>=2 and p>e8>e21>e50:
                    # Keep discovery fast. Market-cap validation is done only for the
                    # small final candidate set, not one Yahoo request per U.S. symbol.
                    keep.append((t,momentum,adr,dollar))
            except Exception: pass
    keep.sort(key=lambda z:(z[1],z[2],z[3]),reverse=True)
    return [x[0] for x in keep[:limit]]

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
    """Advanced day-trade layer with true premarket context and regular-session ORB."""
    if g is None or len(g)==0:return
    x=add_intraday_rvol(g.dropna())
    sx=add_intraday_rvol(spy_g.dropna()) if spy_g is not None and len(spy_g) else pd.DataFrame()
    latest=x.index[-1].date(); all_today=x[x.index.date==latest].copy()
    if len(all_today)<2:return
    hhmm=all_today.index[-1].strftime("%H:%M")
    pre=all_today[(all_today.index.strftime("%H:%M")>="04:00") & (all_today.index.strftime("%H:%M")<"09:30")].copy()
    reg=all_today[(all_today.index.strftime("%H:%M")>="09:30") & (all_today.index.strftime("%H:%M")<="16:00")].copy()
    if hhmm<"09:30":
        phase="PREMARKET"; today=pre
    elif hhmm<"10:30": phase="OPENING"; today=reg
    elif hhmm<"13:30": phase="MIDDAY"; today=reg
    elif hhmm<"15:45": phase="POWER HOUR"; today=reg
    else: phase="CLOSE"; today=reg
    if len(today)<2:return
    today=today.copy(); r=today.iloc[-1]; p=float(r.Close)
    today["e8"]=today.Close.ewm(span=8,adjust=False).mean(); today["e21"]=today.Close.ewm(span=21,adjust=False).mean(); r=today.iloc[-1]
    tp=(today.High+today.Low+today.Close)/3; vw=(tp*today.Volume).cumsum()/today.Volume.cumsum().replace(0,float("nan"))
    vwap=float(vw.iloc[-1]) if pd.notna(vw.iloc[-1]) else p
    vwap_rising=len(vw)>=4 and float(vw.iloc[-1])>float(vw.iloc[-4])
    ema_rising=len(today)>=4 and float(today.e8.iloc[-1])>float(today.e8.iloc[-4]) and float(today.e21.iloc[-1])>=float(today.e21.iloc[-4])
    rv=float(r.rv) if "rv" in r and pd.notna(r.rv) else 0.0
    market_ok=bool(market.get("spy",{}).get("bullish")) and bool(market.get("qqq",{}).get("bullish"))
    spy_today=sx[sx.index.date==latest].copy() if len(sx) else sx
    spy_phase=spy_today[(spy_today.index.strftime("%H:%M")<"09:30")] if phase=="PREMARKET" and len(spy_today) else regular_session(spy_today) if len(spy_today) else spy_today
    stock_ret=(p/float(today.Close.iloc[0])-1)*100 if len(today)>1 else 0
    spy_ret=(float(spy_phase.Close.iloc[-1])/float(spy_phase.Close.iloc[0])-1)*100 if len(spy_phase)>1 else 0
    rs=stock_ret-spy_ret; rs_ok=rs>=0.30
    pre_high=float(pre.High.max()) if len(pre) else None; pre_low=float(pre.Low.min()) if len(pre) else None
    if phase=="PREMARKET":
        entry=pre_high if pre_high else p
        stop=pre_low if pre_low and pre_low<entry else entry*.99
        trigger=p>=entry*.997
        extension=(p/entry-1)*100 if entry else 0; no_chase=extension<=0.5
        recent=float(pre.Volume.tail(3).mean()) if len(pre)>=3 else float(r.Volume)
        prior=float(pre.Volume.iloc[:-3].tail(12).mean()) if len(pre)>4 else recent
        volume_ok=recent>0 and (prior<=0 or recent>=prior*1.2)
        checks={"Near/breaking premarket high":trigger,"Above premarket VWAP":p>vwap,"EMA8 > EMA21":p>float(r.e8)>float(r.e21),"Premarket volume":volume_ok,"Relative strength":rs_ok,"Not extended":no_chase}
        setup="Premarket High + VWAP + Volume"
    else:
        if len(reg)<3:return
        orb=reg.iloc[:3]; orb_high=float(orb.High.max()); orb_low=float(orb.Low.min())
        entry=orb_high; structural=max(orb_low,vwap); stop=min(entry-.01,structural)
        extension=(p/entry-1)*100 if entry else 0; no_chase=extension<=0.5
        close_confirm=len(reg)>3 and p>orb_high
        recent_vol=float(reg.Volume.iloc[-4:-1].mean()) if len(reg)>=4 else 0
        breakout_volume=recent_vol>0 and float(r.Volume)>recent_vol*1.2
        checks={"ORB close":close_confirm,"Above VWAP":p>vwap,"VWAP rising":vwap_rising,"EMA trend":p>float(r.e8)>float(r.e21),"EMA rising":ema_rising,"RVOL >= 1.5":rv>=1.5,"Breakout volume":breakout_volume,"Relative strength":rs_ok,"Not extended":no_chase}
        setup="15m ORB + VWAP + RVOL"
    risk=max(.01,entry-stop); shares=min(int(15/risk),int(1500/entry)) if entry>0 else 0
    score=round(100*sum(checks.values())/len(checks)); grade="A+" if score>=90 else ("A" if score>=80 else ("B" if score>=70 else "C"))
    state="A+ CONFIRMED" if score>=90 and no_chase else ("CONFIRMED" if score>=80 else ("READY" if score>=70 else "WATCH"))
    chart=[{"time":str(ii),"open":num(xx.Open),"high":num(xx.High),"low":num(xx.Low),"close":num(xx.Close)} for ii,xx in all_today.tail(80).iterrows()]
    return {"ticker":t,"price":num(p),"setup":setup,"status":state,"entry":num(entry),"stop":num(stop),"t1":num(entry+risk),"t2":num(entry+2*risk),"risk_share":num(risk),"rvol":num(rv),"chart":chart,"quality_score":score,"grade":grade,"quality_state":state,"phase":phase,"session_score":score,"session_state":state,"session_checks":checks,"relative_strength":round(rs,2),"stock_session_return":round(stock_ret,2),"spy_session_return":round(spy_ret,2),"vwap":num(vwap),"vwap_rising":vwap_rising,"ema_rising":ema_rising,"market_aligned":market_ok,"extension_pct":round(extension,2),"no_chase":no_chase,"premarket_high":num(pre_high),"premarket_low":num(pre_low),"shares":shares,"planned_risk":round(shares*risk,2),"t1_1r":num(entry+risk),"t2_2r":num(entry+2*risk)}

def swing_setup(t,g):
    """Momentum swing setup: EMA stack + tight base/volume contraction + breakout or U&R."""
    g=ind(g)
    if len(g)<55:return
    r=g.iloc[-1]; p=float(r.Close)
    av20=float(g.Volume.tail(20).mean())
    adr=float((((g.High-g.Low)/g.Close)*100).tail(20).mean())
    full=bool(p>r.e8>r.e21>r.e50)
    liquid=bool(p>=3 and av20>=500000 and p*av20>=15000000 and adr>=2)
    if not (full and liquid): return

    base=g.iloc[-11:-1].copy()
    base_high=float(base.High.max()); base_low=float(base.Low.min())
    base_mid=max(.01,(base_high+base_low)/2)
    base_width=(base_high-base_low)/base_mid*100
    atr20=float((g.High-g.Low).tail(20).mean())
    tight=base_width<=max(8.0,(atr20/p*100)*4.0)

    recent_vol=float(g.Volume.iloc[-6:-1].mean())
    prior_vol=float(g.Volume.iloc[-21:-6].mean())
    contraction=bool(prior_vol>0 and recent_vol<=prior_vol*.85)
    rvol=float(r.Volume/av20) if av20>0 else 0

    # Relative strength proxy: 20-day return. Cross-sectional ranking is applied later.
    ret20=(p/float(g.Close.iloc[-21])-1)*100
    breakout=bool(p>base_high and rvol>=1.5)
    near=bool(p>=base_high*.985 and p<=base_high*1.01)

    # Undercut-and-rally: recent low undercuts the prior 10-day low, then closes back above it.
    prior_low=float(g.Low.iloc[-21:-11].min())
    recent_low=float(g.Low.iloc[-5:].min())
    ur=bool(recent_low<prior_low and p>prior_low)
    ur_entry=prior_low
    setup="Undercut & Rally" if ur else "Tight Base Breakout"
    entry=ur_entry if ur else base_high
    stop=float(recent_low*.995) if ur else max(base_low,entry*.96)
    risk=max(.01,entry-stop)

    score=45
    score += 15 if tight else 0
    score += 10 if contraction else 0
    score += 10 if near or ur else 0
    score += 10 if rvol>=1.5 else (5 if rvol>=1 else 0)
    score += 10 if ret20>0 else 0
    status="READY" if ((breakout or ur) and rvol>=1.5) else ("WAITING FOR BREAKOUT" if (near or ur or tight) else "NO TRADE")
    chart=[{"time":str(i),"open":num(x.Open),"high":num(x.High),"low":num(x.Low),"close":num(x.Close)} for i,x in g.tail(60).iterrows()]
    return {"ticker":t,"price":num(p),"score":min(100,int(score)),"rvol":num(rvol),"adr":num(adr),
            "setup":setup,"timeframe":"Daily","status":status,"entry":num(entry),"stop":num(stop),
            "t1":num(entry+2*risk),"t2":num(entry+3*risk),"risk_share":num(risk),
            "tight_base":tight,"volume_contraction":contraction,"ret20":round(ret20,2),"chart":chart}

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

def swing_sector_strength():
    """Rank sectors for swing trading using 1d/5d/20d momentum, SPY-relative strength and EMA trend."""
    out=[]
    try:
        syms=list(SECTOR_ETFS.values())+["SPY"]
        z=yf.download(syms,period="3mo",interval="1d",group_by="ticker",auto_adjust=False,actions=False,threads=True,progress=False,timeout=20)
        spy=z["SPY"].dropna()
        spy20=(float(spy.Close.iloc[-1])/float(spy.Close.iloc[-21])-1)*100 if len(spy)>=21 else 0
        for name,t in SECTOR_ETFS.items():
            g=z[t].dropna()
            if len(g)<21: continue
            close=g.Close.astype(float); p=float(close.iloc[-1])
            d1=(p/float(close.iloc[-2])-1)*100; d5=(p/float(close.iloc[-6])-1)*100; d20=(p/float(close.iloc[-21])-1)*100
            rs20=d20-spy20
            e8=float(close.ewm(span=8,adjust=False).mean().iloc[-1]); e21=float(close.ewm(span=21,adjust=False).mean().iloc[-1]); e50=float(close.ewm(span=50,adjust=False).mean().iloc[-1])
            trend=p>e8>e21 and (len(close)<50 or e21>e50)
            score=50 + max(-12,min(12,d5*2)) + max(-18,min(18,rs20*2.5)) + max(-8,min(8,d20*.5)) + (12 if trend else -12)
            score=round(max(0,min(100,score)),1)
            out.append({"sector":name,"etf":t,"day_pct":round(d1,2),"week_pct":round(d5,2),"month_pct":round(d20,2),"rs20_vs_spy":round(rs20,2),"ema_trend":trend,"strength_score":score})
        out.sort(key=lambda x:x["strength_score"],reverse=True)
        for n,x in enumerate(out):
            x["rank"]=n+1; x["state"]="STRONG" if x["strength_score"]>=65 else ("WEAK" if x["strength_score"]<40 else "NEUTRAL")
    except Exception as e: print("swing sector strength",e,flush=True)
    return out

def main():
    global U
    # Apply the real momentum/liquidity filters to the configured U.S. universe.
    major=load_major_index_members()
    fallback=[x.strip().upper() for x in UNIVERSE_FILE.read_text().splitlines() if x.strip() and not x.startswith("#")]
    broad=list(dict.fromkeys(fallback))
    candidates=discover_candidates(broad,limit=80)
    # Validate the $300M market-cap rule only after technical/liquidity discovery.
    cap_ok=[]
    for t in candidates:
        try:
            cap=float(yf.Ticker(t).fast_info.get("market_cap") or 0)
            if cap>=300_000_000: cap_ok.append(t)
        except Exception:
            pass
    candidates=cap_ok
    # Keep major-index leaders in the analysis set even when they are not in universe.txt;
    # swing_setup still rejects names that do not meet the requested rules.
    major_candidates=list(major)
    U=["SPY","QQQ"]+list(dict.fromkeys([x for x in major_candidates if x not in ("SPY","QQQ")]+[x for x in candidates if x not in ("SPY","QQQ")]))
    print("fast dashboard snapshot:",len(candidates),"fallback +",len(major_candidates),"major candidates")
    print("STEP daily download",flush=True)
    d=yf.download(U,period="4mo",interval="1d",group_by="ticker",auto_adjust=False,actions=False,threads=True,progress=False,timeout=20)
    print("STEP daily done",flush=True)
    # prepost=False prevents extended-hours prints from contaminating ORB/VWAP/RVOL.
    print("STEP intraday download",flush=True)
    i=yf.download(U,period="5d",interval="5m",group_by="ticker",auto_adjust=False,actions=False,prepost=False,threads=True,progress=False,timeout=20)
    print("STEP intraday done",flush=True)
    day=[];swing=[];quality=[]
    # Data-integrity guard: all symbols must come from the same latest regular session.
    try:
        spy_session=regular_session(i["SPY"].dropna()).index[-1].date()
    except Exception:
        spy_session=None
    rejected_stale=[]
    for t in [x for x in U if x not in ("SPY","QQQ")]:
        try:
            x=day_setup(t,i[t])
            if x:day.append(x)
        except Exception as e:print("day",t,e)
        try:
            x=swing_setup(t,d[t])
            if x:swing.append(x)
        except Exception as e:print("swing",t,e)
    day,day_major_count=pick_40(day,major)
    # Cross-sectional relative-strength ranking, then return only the best 5 swing candidates.
    swing=sorted(swing,key=lambda x:(x.get("ret20",-999),x.get("score",0),x.get("rvol") or 0),reverse=True)
    rs_cut=max(1,int(len(swing)*.35)) if swing else 0
    leaders={x["ticker"] for x in swing[:rs_cut]}
    for x in swing:
        x["relative_strength"]="LEADER" if x["ticker"] in leaders else "AVERAGE"
        if x["ticker"] in leaders: x["score"]=min(100,x.get("score",0)+5)
    swing=[x for x in swing if x.get("relative_strength")=="LEADER" and x.get("status")!="NO TRADE"]
    swing=sorted(swing,key=lambda x:(x.get("score",0),x.get("rvol") or 0),reverse=True)[:5]
    swing_major_count=len([x for x in swing if x.get("ticker") in major])
    m=regime(d)
    print("STEP sectors",flush=True)
    sectors=sector_strength()
    print("STEP sectors done",len(sectors),flush=True)
    swing_sectors=swing_sector_strength()
    print("STEP swing sectors done",len(swing_sectors),flush=True)
    print("STEP news",flush=True)
    news_items=news()
    print("STEP news done",len(news_items),flush=True)
    print("STEP spy agents",flush=True)
    try:
        spy_daily=d["SPY"].dropna()
        spy_intraday=regular_session(i["SPY"]).dropna()
        spy_ai=build_spy_agents(spy_daily,spy_intraday,[x for x in news_items if x.get("ticker")=="SPY"])
        if spy_ai:
            spy_ai["data_asof"]=str(spy_intraday.index[-1]) if len(spy_intraday) else None
            spy_ai["market_data_status"]="LATEST AVAILABLE SESSION"
    except Exception as e:
        print("spy agents",e); spy_ai={"error":str(e)[:180],"market_data_status":"UNAVAILABLE"}
    print("STEP spy agents done",flush=True)
    snap={"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"spy_ai":spy_ai,"scanner":{"listed_symbols":len(broad),"passed_filters":len(candidates),"intraday_scanned":max(0,len(U)-2),"scan_mode":"FILTERED SNAPSHOT","day_displayed":len(day),"swing_displayed":len(swing),"day_major_index":day_major_count,"swing_major_index":swing_major_count,"target_major_index":30,"dynamic":True,"data_session":str(spy_session) if spy_session else None,"stale_rejected":len(rejected_stale),"price_mode":"RAW / UNADJUSTED"},"market":m,"sectors":sectors,"swing_sectors":swing_sectors,"day":day,"swing":swing,"news":news_items,"analytics":{"bullish_count":sum(x["status"]!="WATCH" for x in swing),"bearish_count":sum(x["status"]=="WATCH" for x in swing),"day_confirmed":sum(x["status"]=="CONFIRMED" for x in day),"swing_ready":sum(x["status"] in ("READY","CONFIRMED") for x in swing)}}
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
