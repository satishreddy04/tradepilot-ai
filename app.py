import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="TradePilot AI",page_icon="📈",layout="wide")
st.markdown("""<style>
.stApp{background:#07111f;color:#e8eef7}.block-container{padding-top:1rem;max-width:1500px}
[data-testid="stMetric"]{background:#0d1b2d;border:1px solid #20324a;padding:12px;border-radius:14px;min-height:96px}
[data-testid="stMetricValue"]{font-size:1.45rem!important;white-space:normal!important;overflow:visible!important}
.card{background:#0d1b2d;border:1px solid #20324a;border-radius:16px;padding:15px;margin-bottom:10px}.muted{color:#8ea2bc}
.status{display:inline-block;padding:3px 8px;border:1px solid #304761;border-radius:999px;font-size:.8rem}
@media(max-width:700px){
 .block-container{padding:.6rem .75rem 2rem}.stApp h1{font-size:1.75rem}
 [data-testid="stHorizontalBlock"]{gap:.45rem}
 [data-testid="stMetric"]{padding:9px;min-height:82px}
 [data-testid="stMetricLabel"]{font-size:.72rem}
 [data-testid="stMetricValue"]{font-size:1.05rem!important}
 div[data-testid="stDataFrame"]{font-size:.78rem}
 .card{padding:11px}
}
</style>""",unsafe_allow_html=True)

p=Path("docs/data/snapshot.json")
try:s=json.loads(p.read_text())
except:s={"generated_at":None,"market":{"label":"WAITING FOR SCAN","score":50},"day":[],"swing":[],"news":[],"analytics":{}}
m=s.get("market",{})

def short_time(v):
    if not v:return "Not built"
    try:return datetime.fromisoformat(v.replace("Z","+00:00")).strftime("%b %d %H:%M UTC")
    except:return str(v)[:16]

st.title("📈 TradePilot AI")
st.caption("Market regime • Day & swing setups • targets/stops • analytics • news")

# Two rows prevent truncation on phones and remain clean on desktop.
r1=st.columns(3)
r1[0].metric("Market",m.get("label","UNKNOWN"))
r1[1].metric("Score",f'{m.get("score",0)}/100')
r1[2].metric("Breadth",f'{m.get("breadth","—")}%' if m.get("breadth") is not None else "—")
r2=st.columns(3)
r2[0].metric("SPY",m.get("spy",{}).get("price","—"))
r2[1].metric("QQQ",m.get("qqq",{}).get("price","—"))
r2[2].metric("Snapshot",short_time(s.get("generated_at")))

st.markdown('<div class="card"><b>Overall Market: '+str(m.get("label","UNKNOWN"))+'</b><br><span class="muted">Rules-based SPY/QQQ EMA structure + watchlist breadth; not a forecast.</span></div>',unsafe_allow_html=True)
scan=s.get("scanner",{})
if scan:
    st.markdown('<div class="card"><b>Dynamic Market Scanner</b><br><span class="muted">Scanned <b>'+str(scan.get("listed_symbols","—"))+'</b> U.S.-listed symbols → <b>'+str(scan.get("passed_filters","—"))+'</b> passed liquidity/momentum filters → <b>'+str(scan.get("intraday_scanned","—"))+'</b> received intraday analysis → Top <b>'+str(scan.get("day_displayed","—"))+'</b> Day / <b>'+str(scan.get("swing_displayed","—"))+'</b> Swing displayed.</span></div>',unsafe_allow_html=True)

def setups(rows,title,day_mode=False):
    st.subheader(title)
    if not rows:
        st.info("Waiting for the next market-data snapshot.");return
    df=pd.DataFrame(rows)
    cols=[x for x in ["ticker","price","score","rvol","setup","status","entry","stop","t1","t2","risk_share"] if x in df]
    st.dataframe(df[cols],use_container_width=True,hide_index=True,height=min(560,72+35*min(len(df),14)))
    t=st.selectbox("Inspect setup",df.ticker.tolist(),key=title)
    r=df[df.ticker==t].iloc[0]
    cd=r.get("chart",[])
    left,right=st.columns([2,1])
    if isinstance(cd,list) and cd:
        d=pd.DataFrame(cd)
        fig=go.Figure(go.Candlestick(x=d.time,open=d.open,high=d.high,low=d.low,close=d.close))
        for k,n in [("entry","Entry"),("stop","Stop"),("t1","T1"),("t2","T2")]:
            if pd.notna(r.get(k)):fig.add_hline(y=float(r[k]),line_dash="dash",annotation_text=n)
        fig.update_layout(height=390,margin=dict(l=5,r=5,t=20,b=5),paper_bgcolor="#0d1b2d",plot_bgcolor="#0d1b2d",font_color="#cbd7e6",xaxis_rangeslider_visible=False)
        left.plotly_chart(fig,use_container_width=True)
    risk=float(r.get("risk_share",0) or 0);risk_budget=15.0;shares_by_risk=int(risk_budget/risk) if risk>0 else 0;entry=float(r.get("entry",0) or 0);shares_by_cash=int(1500/entry) if entry>0 else 0;shares=min(shares_by_risk,shares_by_cash)
    extra=""
    if day_mode:
        extra="<br>VWAP: <b>$"+str(r.get("vwap","—"))+"</b><br>ORB H/L: <b>$"+str(r.get("orb_high","—"))+" / $"+str(r.get("orb_low","—"))+"</b>"
    right.markdown('<div class="card"><b>'+str(r.ticker)+'</b> · <span class="status">'+str(r.get("status",""))+'</span><hr>Setup: <b>'+str(r.get("setup",""))+'</b><br>Score: <b>'+str(r.get("score",""))+'/100</b><br>RVOL: <b>'+str(r.get("rvol","—"))+'x</b>'+extra+'<hr>Entry: <b>$'+str(r.get("entry","—"))+'</b><br>Stop: <b>$'+str(r.get("stop","—"))+'</b><br>T1: <b>$'+str(r.get("t1","—"))+'</b><br>T2: <b>$'+str(r.get("t2","—"))+'</b><br>Risk/share: <b>$'+format(risk,'.2f')+'</b><br>Max shares @ $15 risk / $1,500 cash: <b>'+str(shares)+'</b></div>',unsafe_allow_html=True)

day,swing,analytics,backtest,news=st.tabs(["⚡ Day Trades","📆 Swing Trades","📊 Analytics","🧪 Backtest","📰 News & Catalysts"])
with day:setups(s.get("day",[]),"Top Day Trade Setups",True)
with swing:setups(s.get("swing",[]),"Top Swing Trade Setups")
with analytics:
    a=s.get("analytics",{})
    cc=st.columns(2)
    cc[0].metric("Bullish watchlist",a.get("bullish_count",0));cc[1].metric("Bearish watchlist",a.get("bearish_count",0))
    cc=st.columns(2)
    cc[0].metric("Day confirmed",a.get("day_confirmed",0));cc[1].metric("Swing ready+",a.get("swing_ready",0))
with backtest:
    st.subheader("Historical Strategy Backtest")
    bp=Path("docs/data/backtest.json")
    if not bp.exists():
        st.error("Backtest data file is not available yet.")
    else:
        bt=json.loads(bp.read_text())
        bs=bt.get("summary",{})
        trades=pd.DataFrame(bt.get("trades",[]))
        st.caption("Research simulation only — historical results are not a forecast.")
        a1,a2,a3=st.columns(3)
        a1.metric("Starting Balance",f"$"+format(float(bs.get("starting_equity",0)),",.2f"))
        a2.metric("Ending Balance",f"$"+format(float(bs.get("ending_equity",0)),",.2f"))
        a3.metric("Net P&L",f"$"+format(float(bs.get("net_pnl",0)),",.2f"))
        b1,b2,b3=st.columns(3)
        b1.metric("Trades",bs.get("trades",0))
        b2.metric("Win Rate",f'{bs.get("win_rate",0)}%')
        b3.metric("Profit Factor",bs.get("profit_factor","—"))
        st.metric("Max Drawdown",f"$"+format(float(bs.get("max_drawdown_dollars",0)),",.2f"))
        if not trades.empty:
            fig=go.Figure(go.Scatter(x=list(range(1,len(trades)+1)),y=trades["equity"],mode="lines"))
            fig.update_layout(title="Equity Curve",height=350,margin=dict(l=5,r=5,t=45,b=5),paper_bgcolor="#0d1b2d",plot_bgcolor="#0d1b2d",font_color="#cbd7e6")
            st.plotly_chart(fig,use_container_width=True)
            wanted=[x for x in ["date","ticker","entry","stop","exit","reason","shares","pnl","equity"] if x in trades.columns]
            st.dataframe(trades[wanted].iloc[::-1],use_container_width=True,hide_index=True,height=430)
        st.warning("This first backtest is preliminary. Some historical trades exceed a $500 account's realistic buying power because of extremely tight stops. We will correct position sizing before evaluating the strategy.")

with news:
    if not s.get("news"):st.info("No current catalysts in snapshot.")
    for n in s.get("news",[])[:30]:
        st.markdown('<div class="card"><b>'+str(n.get("ticker","MARKET"))+'</b> — '+str(n.get("title",""))+'<br><span class="muted">'+str(n.get("publisher",""))+' · '+str(n.get("published",""))+'</span><br><a href="'+str(n.get("link","#"))+'" target="_blank">Open source</a></div>',unsafe_allow_html=True)
st.caption("Yahoo/yfinance is unofficial and may be delayed, throttled or unavailable. Confirm prices with your broker before trading.")
