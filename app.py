import os
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="TradePilot AI", page_icon="📈", layout="wide")
st.markdown("""<style>
.stApp{background:#07111f;color:#e8eef7}.block-container{padding-top:1.2rem;max-width:1500px}
[data-testid="stMetric"]{background:#0d1b2d;border:1px solid #20324a;padding:14px;border-radius:14px}
.tp{background:#0d1b2d;border:1px solid #20324a;border-radius:16px;padding:16px;margin-bottom:12px}
.ok{color:#35d07f}.warn{color:#f6c453}.muted{color:#8ea2bc}.badge{padding:4px 9px;border-radius:99px;background:#142942;font-size:12px}
</style>""",unsafe_allow_html=True)

for k,v in {"auto":False,"killed":False,"alerts":[]}.items():
    if k not in st.session_state: st.session_state[k]=v

def rows(kind):
    rng=np.random.default_rng(42 if kind=="DAY" else 84)
    syms="NVDA AMD PLTR ANET AVGO ARM SMCI CRWD NET MU TSLA META AMZN GOOGL APP HOOD COIN RKLB VRT DELL MRVL CLS ALAB TGTX BE".split()
    out=[]
    for s in syms:
        p=round(float(rng.uniform(18,330)),2); score=int(rng.integers(66,97)); rv=round(float(rng.uniform(.7,3.2)),2)
        risk=round(max(.25,p*float(rng.uniform(.008,.025))),2); trig=round(p*(1+float(rng.uniform(.001,.018))),2)
        status="CONFIRMED" if score>=93 and rv>=1.5 else ("READY" if score>=82 else "WATCH")
        out.append([s,p,score,rv,"ORB/VWAP" if kind=="DAY" else "Tight Base",trig,round(trig-risk,2),round(trig+2*risk,2),round(trig+3*risk,2),status])
    d=pd.DataFrame(out,columns=["Ticker","Price","Score","RVOL","Setup","Trigger","Stop","T1","T2","Status"])
    return d.sort_values(["Score","RVOL"],ascending=False).reset_index(drop=True)

def chart(r):
    x=pd.date_range(end=pd.Timestamp.now(),periods=40,freq="5min")
    rng=np.random.default_rng(abs(hash(r.Ticker))%(2**32))
    y=r.Price*np.cumprod(1+rng.normal(.0003,.003,40))
    f=go.Figure(go.Scatter(x=x,y=y,mode="lines"))
    f.add_hline(y=r.Trigger,line_dash="dash",annotation_text="Trigger")
    f.add_hline(y=r.Stop,line_dash="dot",annotation_text="Stop")
    f.update_layout(height=300,margin=dict(l=8,r=8,t=20,b=8),paper_bgcolor="#0d1b2d",plot_bgcolor="#0d1b2d",font_color="#cbd7e6",showlegend=False)
    return f

st.title("📈 TradePilot AI")
st.caption("Top-25 scanners • Alerts • Manual execution • Paper AUTO")
m=st.columns(5)
m[0].metric("Account","USD 500");m[1].metric("Today's P&L","USD 0");m[2].metric("Open Risk","USD 0")
m[3].metric("Daily Loss Limit","USD 10");m[4].metric("Last Scan",datetime.now().strftime("%I:%M %p"))

a,b=st.columns(2)
a.markdown('<div class="tp"><b>SPY</b> <span class="badge ok">GREEN</span><br><span class="muted">Demo regime</span><br>Price &gt; EMA8 &gt; EMA21 &gt; EMA50</div>',unsafe_allow_html=True)
b.markdown('<div class="tp"><b>QQQ</b> <span class="badge ok">GREEN</span><br><span class="muted">Demo regime</span><br>Price &gt; EMA8 &gt; EMA21 &gt; EMA50</div>',unsafe_allow_html=True)
st.caption("Demo data is shown until a market-data provider is configured.")

x,y,z=st.columns([1,1,2])
manual=x.toggle("Manual",value=True)
st.session_state.auto=y.toggle("Paper AUTO",value=st.session_state.auto,disabled=st.session_state.killed)
if z.button("🛑 KILL AUTO TRADING",type="primary",use_container_width=True):
    st.session_state.auto=False;st.session_state.killed=True;st.session_state.alerts.insert(0,"AUTO disabled by kill switch")
if st.session_state.killed and st.button("Reset kill switch"): st.session_state.killed=False

def scanner(df,title,key):
    st.subheader(title)
    c1,c2,c3=st.columns(3)
    ms=c1.slider("Min score",50,100,75,key=key+"s"); mr=c2.slider("Min RVOL",0.,5.,1.,.1,key=key+"r")
    states=c3.multiselect("Status",["CONFIRMED","READY","WATCH"],default=["CONFIRMED","READY","WATCH"],key=key+"st")
    v=df[(df.Score>=ms)&(df.RVOL>=mr)&df.Status.isin(states)].copy()
    v.insert(0,"Rank",range(1,len(v)+1));st.dataframe(v,use_container_width=True,hide_index=True)
    if len(v):
        t=st.selectbox("Inspect",v.Ticker,key=key+"t");r=v[v.Ticker==t].iloc[0]
        l,rr=st.columns([2,1]);l.plotly_chart(chart(r),use_container_width=True)
        risk=round(r.Trigger-r.Stop,2);maxrisk=float(os.getenv("MAX_RISK_PER_TRADE","5"));shares=max(0,int(maxrisk/risk)) if risk else 0
        rr.markdown(f'<div class="tp"><b>{r.Ticker}</b> <span class="badge">{r.Status}</span><br><br>Score <b>{r.Score}/100</b> · RVOL <b>{r.RVOL}x</b><hr>Trigger <b>USD {r.Trigger}</b><br>Stop <b>USD {r.Stop}</b><br>T1 <b>USD {r.T1}</b><br>T2 <b>USD {r.T2}</b><br><br>Risk/share <b>USD {risk}</b><br>Max shares at USD {maxrisk} risk: <b>{shares}</b></div>',unsafe_allow_html=True)
        if manual and rr.button("Prepare paper order",key=key+"o"):
            st.session_state.alerts.insert(0,f"{r.Ticker}: paper order prepared, {shares} shares at trigger {r.Trigger}")
            rr.success("Prepared. Broker submission activates after Alpaca paper credentials are configured.")

day,swing,alerts,pos,settings=st.tabs(["⚡ Day","📆 Swing","🔔 Alerts","💼 Positions","⚙️ Settings"])
with day: scanner(rows("DAY"),"Top 25 Day Trades","d")
with swing: scanner(rows("SWING"),"Top 25 Swing Trades","w")
with alerts:
    st.subheader("Alerts")
    st.info("Designed for WATCH → READY → CONFIRMED alerts. Telegram activates after credentials are added.")
    if st.button("Generate test alert"): st.session_state.alerts.insert(0,"TEST: alert channel working")
    for q in st.session_state.alerts[:30]: st.write("🔔",q)
with pos:
    st.subheader("Positions")
    st.dataframe(pd.DataFrame(columns=["Ticker","Qty","Entry","Last","Stop","T1","T2","P&L"]),use_container_width=True)
with settings:
    st.subheader("Risk & Connections")
    st.number_input("Account size",100.,value=500.,step=50.)
    st.number_input("Max risk/trade",1.,value=float(os.getenv("MAX_RISK_PER_TRADE","5")),step=1.)
    st.number_input("Max daily loss",1.,value=float(os.getenv("MAX_DAILY_LOSS","10")),step=1.)
    st.write("Alpaca:","🟢 configured" if os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY") else "🟡 demo mode")
    st.write("Telegram:","🟢 configured" if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID") else "🟡 not configured")
    st.warning("V1 keeps live-money AUTO disabled. Validate paper trading first.")
