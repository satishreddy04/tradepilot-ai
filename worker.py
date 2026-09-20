import json,os
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import yfinance as yf
import requests
U="SPY QQQ NVDA AMD PLTR ANET AVGO ARM SMCI CRWD NET MU TSLA META AMZN GOOGL APP HOOD COIN RKLB VRT DELL MRVL CLS ALAB TGTX BE".split();OUT=Path("docs/data/snapshot.json")
def num(x):
 try:return None if pd.isna(x) else round(float(x),2)
 except:return None
def ind(g):
 g=g.copy().dropna();g["e8"]=g.Close.ewm(span=8,adjust=False).mean();g["e21"]=g.Close.ewm(span=21,adjust=False).mean();g["e50"]=g.Close.ewm(span=50,adjust=False).mean();g["av"]=g.Volume.rolling(20).mean();g["rv"]=g.Volume/g.av;return g
def setup(t,g,kind):
 g=ind(g)
 if len(g)<21:return
 r=g.iloc[-1];p=float(r.Close);trend=p>r.e8>r.e21;full=trend and r.e21>r.e50;rv=float(r.rv) if pd.notna(r.rv) else 0;look=20 if kind=="swing" else 12
 ph=float(g.High.shift(1).rolling(look).max().iloc[-1]);lo=float(g.Low.tail(10).min());near=p>=ph*.985
 score=(35 if full else 20 if trend else 0)+(25 if rv>=1.5 else 12 if rv>=1 else 0)+(25 if near else 0)+15
 status="CONFIRMED" if p>ph and rv>=1.5 and trend else ("READY" if trend and near else "WATCH");entry=ph;stop=max(lo,entry*(.985 if kind=="day" else .96));risk=max(.01,entry-stop)
 chart=[{"time":str(i),"open":num(x.Open),"high":num(x.High),"low":num(x.Low),"close":num(x.Close)} for i,x in g.tail(50).iterrows()]
 return {"ticker":t,"price":num(p),"score":min(100,int(score)),"rvol":num(rv),"setup":"ORB / momentum breakout" if kind=="day" else "EMA trend / 20-bar breakout","status":status,"entry":num(entry),"stop":num(stop),"t1":num(entry+2*risk),"t2":num(entry+3*risk),"risk_share":num(risk),"chart":chart}
def regime(d):
 vals={};bull=0
 for t in ["SPY","QQQ"]:
  try:g=ind(d[t]);r=g.iloc[-1];ok=bool(r.Close>r.e8>r.e21>r.e50);bull+=int(ok);vals[t.lower()]={"price":num(r.Close),"bullish":ok}
  except:vals[t.lower()]={}
 breadth=[]
 for t in U[2:]:
  try:g=ind(d[t]);r=g.iloc[-1];breadth.append(bool(r.Close>r.e21))
  except:pass
 b=round(100*sum(breadth)/len(breadth)) if breadth else 50;score=round(bull/2*60+b*.4);label="BULLISH" if score>=65 else ("BEARISH" if score<=35 else "NEUTRAL / MIXED")
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
 d=yf.download(U,period="4mo",interval="1d",group_by="ticker",threads=True,progress=False);i=yf.download(U,period="5d",interval="5m",group_by="ticker",prepost=True,threads=True,progress=False)
 day=[];swing=[]
 for t in U[2:]:
  try:
   x=setup(t,i[t],"day")
   if x:day.append(x)
  except:pass
  try:
   x=setup(t,d[t],"swing")
   if x:swing.append(x)
  except:pass
 day=sorted(day,key=lambda x:(x["score"],x["rvol"] or 0),reverse=True)[:25];swing=sorted(swing,key=lambda x:(x["score"],x["rvol"] or 0),reverse=True)[:25];m=regime(d)
 snap={"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"market":m,"day":day,"swing":swing,"news":news(),"analytics":{"bullish_count":sum(x["status"]!="WATCH" for x in swing),"bearish_count":sum(x["status"]=="WATCH" for x in swing),"day_confirmed":sum(x["status"]=="CONFIRMED" for x in day),"swing_ready":sum(x["status"] in ("READY","CONFIRMED") for x in swing)}}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(snap,separators=(",",":")))
 token=os.getenv("TELEGRAM_BOT_TOKEN");chat=os.getenv("TELEGRAM_CHAT_ID");confirmed=[x for x in day if x["status"]=="CONFIRMED"][:3]
 if token and chat and confirmed:
  msg="TradePilot DAY confirmed\n"+"\n".join(x["ticker"]+": entry "+str(x["entry"])+" stop "+str(x["stop"])+" T1 "+str(x["t1"])+" T2 "+str(x["t2"]) for x in confirmed);requests.post("https://api.telegram.org/bot"+token+"/sendMessage",data={"chat_id":chat,"text":msg},timeout=15)
 print("built",m["label"],len(day),len(swing))
if __name__=="__main__":main()
