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
    view=df[cols].copy()
    def status_style(row):
        status=str(row.get("status","")).upper()
        if status=="CONFIRMED":
            return ["background-color:#123d2a;color:#7CFFB2;font-weight:700" for _ in row]
        if status=="READY":
            return ["background-color:#44370d;color:#FFE082;font-weight:700" for _ in row]
        return ["" for _ in row]
    styled=view.style.apply(status_style,axis=1)
    st.dataframe(styled,use_container_width=True,hide_index=True,height=min(560,72+35*min(len(df),14)))
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

day,swing,spyopt,paper,analytics,backtest,news=st.tabs(["⚡ Day Trades","📆 Swing Trades","🎯 SPY Options AI","📝 Paper Trades","📊 Analytics","🧪 Backtest","📰 News & Catalysts"])
with day:setups(s.get("day",[]),"Top Day Trade Setups",True)
with swing:setups(s.get("swing",[]),"Top Swing Trade Setups")
with spyopt:
    st.subheader("🎯 SPY Options AI — Multi-Agent Analysis")
    ai=s.get("spy_ai",{})
    if not ai:
        st.info("Waiting for the next scanner run to build SPY agent analysis.")
    else:
        dec=ai.get("decision",{}); tech=ai.get("technical",{}); risk=ai.get("risk",{})
        x1,x2,x3,x4=st.columns(4)
        x1.metric("SPY",f"$"+str(ai.get("price","—")));x2.metric("Regime",ai.get("regime","—"));x3.metric("State",dec.get("state","—"));x4.metric("Direction",dec.get("direction","WAIT"))
        st.caption("Paper analysis only. CALL/PUT is a rules-based directional bias, not an options order.")
        a1,a2,a3=st.columns(3)
        with a1:
            st.markdown("#### 📈 Technical Agent")
            st.metric("Technical score",f'{tech.get("score","—")}/100')
            st.write(f"EMA 8 / 21 / 50: {tech.get('ema8','—')} / {tech.get('ema21','—')} / {tech.get('ema50','—')}")
            st.write(f"VWAP: {tech.get('vwap','—')} · RSI: {tech.get('rsi','—')} · ATR: {tech.get('atr','—')}")
            st.write("MACD:", "Bullish" if tech.get("macd_bullish") else "Bearish")
        with a2:
            st.markdown("#### 📰 News Agent")
            st.write(ai.get("news",{}).get("status","—"))
            st.write("SPY news items:",ai.get("news",{}).get("items",0))
            st.markdown("#### 💬 Social Agent")
            st.write(ai.get("social",{}).get("status","—"))
        with a3:
            st.markdown("#### 🛡️ Risk Agent")
            st.metric("Max planned risk",f"$"+str(risk.get("max_planned_risk",15)))
            st.write("BLOCKED" if risk.get("blocked") else "PASS")
            st.write(risk.get("reason",""))
            st.metric("Decision confidence",f'{dec.get("confidence","—")}/100')
        b1,b2=st.columns(2)
        with b1:
            st.markdown("#### 🐂 Bull Agent")
            for z in ai.get("bull_case",[]):st.write("•",z)
        with b2:
            st.markdown("#### 🐻 Bear Agent")
            for z in ai.get("bear_case",[]):st.write("•",z)
        opt=ai.get("options",{})
        st.markdown("#### 🧾 Options Chain Agent")
        st.write("Status:",opt.get("status","WAIT"))
        oc=opt.get("candidate")
        if oc:
            q1,q2,q3,q4=st.columns(4)
            q1.metric("Contract",f"{oc.get('type')} {oc.get('strike')}");q2.metric("Expiration",oc.get("expiration","—"));q3.metric("Ask",f"$"+str(oc.get("ask","—")));q4.metric("Max Debit",f"$"+str(oc.get("max_debit","—")))
            st.write(f"DTE: {oc.get('dte')} · Bid/Mid/Ask: {oc.get('bid')} / {oc.get('mid')} / {oc.get('ask')} · Spread: {oc.get('spread_pct')}% · IV: {oc.get('iv_pct')}% · Volume: {oc.get('volume')} · OI: {oc.get('open_interest')}")
        elif opt.get("spread"):
            sp=opt["spread"]
            q1,q2,q3,q4=st.columns(4)
            q1.metric("Strategy",sp.get("type","Debit Spread"));q2.metric("Expiration",sp.get("expiration","—"));q3.metric("Buy / Sell",f"{sp.get('buy_strike')} / {sp.get('sell_strike')}");q4.metric("Est. Debit",f"${sp.get('estimated_debit','—')}")
            st.write(f"Width: ${sp.get('width','—')} · Max loss: ${sp.get('max_loss','—')} · Max profit at expiration: ${sp.get('max_profit','—')}")
            st.warning("Estimated from separate option-leg quotes; verify the live spread bid/ask with your broker before any trade.")
        else:
            st.warning(opt.get("reason","No options candidate while direction is WAIT."))
        st.caption(opt.get("source","Options-chain data must be verified with your broker."))
        st.info("News/social LLM scoring uses real supplied evidence when configured; TradePilot does not fabricate missing social sentiment.")

with paper:
    st.subheader("Paper Trade Journal")
    jp=Path("docs/data/journal.json")
    try: journal=pd.DataFrame(json.loads(jp.read_text())) if jp.exists() else pd.DataFrame()
    except: journal=pd.DataFrame()
    if journal.empty:
        st.info("No paper trades yet. A simulated trade will be created when a Day setup becomes CONFIRMED.")
    else:
        closed=journal[journal["status"]=="CLOSED"] if "status" in journal.columns else pd.DataFrame()
        openj=journal[journal["status"]=="OPEN"] if "status" in journal.columns else pd.DataFrame()
        pnl=float(closed["pnl"].sum()) if not closed.empty and "pnl" in closed.columns else 0
        wins=int((closed["pnl"]>0).sum()) if not closed.empty and "pnl" in closed.columns else 0
        wr=round(100*wins/len(closed),1) if len(closed) else 0
        pc=st.columns(4)
        pc[0].metric("Total Signals",len(journal));pc[1].metric("Open",len(openj));pc[2].metric("Paper P&L",f"$"+format(pnl,",.2f"));pc[3].metric("Win Rate",f"{wr}%")
        st.caption("Simulation only — no broker orders are placed. Entries are created from new CONFIRMED day signals.")
        wanted=[x for x in ["opened_at","ticker","setup","entry","stop","t1","t2","shares","planned_risk","status","t1_hit","outcome","exit","pnl","closed_at"] if x in journal.columns]
        st.dataframe(journal[wanted].iloc[::-1],use_container_width=True,hide_index=True,height=520)

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
