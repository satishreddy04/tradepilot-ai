import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

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

sectors=s.get("sectors",[])
swing_secs=s.get("swing_sectors",[])
st.markdown("### Sector Strength")
left_sec,right_sec=st.columns(2)
with left_sec:
    st.markdown("#### 🔥 Day Trading Sector Strength (Intraday)")
    st.caption("Since market open • vs SPY • VWAP • EMA8/21 • RVOL")
    if sectors:
        dsec=pd.DataFrame(sectors).sort_values("strength_score",ascending=True)
        fig=px.bar(dsec,x="strength_score",y="sector",orientation="h",text="state",hover_data=[x for x in ["etf","intraday_pct","rs_vs_spy","above_vwap","ema_bull","rvol"] if x in dsec.columns])
        fig.update_traces(textposition="inside")
        fig.update_layout(height=420,margin=dict(l=5,r=10,t=5,b=5),xaxis_title="",yaxis_title="",showlegend=False)
        st.plotly_chart(fig,use_container_width=True)
        with st.expander("View all 11 day-trading sectors"):
            st.dataframe(dsec.sort_values("strength_score",ascending=False)[[x for x in ["rank","sector","etf","state","intraday_pct","rs_vs_spy","above_vwap","ema_bull","rvol","strength_score"] if x in dsec]],use_container_width=True,hide_index=True)
    else:
        st.info("Day sector data is waiting for the next scanner snapshot.")
with right_sec:
    st.markdown("#### 📊 Swing Trading Sector Strength (5D / 20D)")
    st.caption("5-day & 20-day momentum • vs SPY • EMA8/21/50 • Swing score")
    if swing_secs:
        ssec=pd.DataFrame(swing_secs).sort_values("strength_score",ascending=True)
        fig2=px.bar(ssec,x="strength_score",y="sector",orientation="h",hover_data=[x for x in ["etf","state","week_pct","month_pct","rs20_vs_spy","ema_trend"] if x in ssec.columns])
        fig2.update_traces(texttemplate="%{x:.0f}",textposition="inside")
        fig2.update_layout(height=420,margin=dict(l=5,r=10,t=5,b=5),xaxis_title="",yaxis_title="",showlegend=False)
        st.plotly_chart(fig2,use_container_width=True)
        with st.expander("View all 11 swing sectors"):
            st.dataframe(ssec.sort_values("strength_score",ascending=False)[[x for x in ["rank","sector","etf","state","week_pct","month_pct","rs20_vs_spy","ema_trend","strength_score"] if x in ssec]],use_container_width=True,hide_index=True)
    else:
        st.info("Swing sector data is waiting for the next successful scanner snapshot.")
st.caption("Sector strength is market context, not a standalone buy signal.")

scan=s.get("scanner",{})
if scan:
    st.markdown('<div class="card"><b>Dynamic Market Scanner</b><br><span class="muted">Scanned <b>'+str(scan.get("listed_symbols","—"))+'</b> U.S.-listed symbols → <b>'+str(scan.get("passed_filters","—"))+'</b> passed liquidity/momentum filters → <b>'+str(scan.get("intraday_scanned","—"))+'</b> received intraday analysis → Top <b>'+str(scan.get("day_displayed","—"))+'</b> Day / <b>'+str(scan.get("swing_displayed","—"))+'</b> Swing displayed. Major-index setups: Day <b>'+str(scan.get("day_major_index","—"))+'</b>, Swing <b>'+str(scan.get("swing_major_index","—"))+'</b> (target 25 Major Index + 25 Broader Market each; shortages are filled only by qualified setups).</span></div>',unsafe_allow_html=True)

def setups(rows,title,day_mode=False):
    st.subheader(title)
    if not rows:
        st.info("Waiting for the next market-data snapshot.");return
    df=pd.DataFrame(rows)
    cols=[x for x in ["ticker","universe","price","score","rvol","setup","status","entry","stop","t1","t2","risk_share"] if x in df]
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

day,quality,swing,spyopt,paper,analytics,backtest,news=st.tabs(["⚡ Day Trades","🧭 Advanced Day Trader","📆 Swing Trades","🎯 SPY Options AI","📝 Paper Trades","📊 Analytics","🧪 Backtest","📰 News & Catalysts"])
with day:setups(s.get("day",[]),"Top 50 Day Trade Setups",True)
with quality:
    st.markdown("## 🧭 Advanced Day Trader")
    st.caption("Session-aware A+ setup engine • Premarket → Opening → Midday → Power Hour → Close • Paper/research mode")
    qr=s.get("quality",[])
    if not qr:
        st.info("Building the Advanced Day Trader snapshot. The next successful scanner run will populate this page.")
    else:
        qdf=pd.DataFrame(qr)
        phases=["🌅 Premarket","🔔 Opening","☀️ Midday","⚡ Power Hour","🏁 Close"]
        active=str(qdf.iloc[0].get("phase","OPENING")).replace("_"," ")
        pc=st.columns(5)
        for col,p in zip(pc,phases):
            with col:
                st.info(p + (" • ACTIVE" if active in p.upper() else ""))
        st.success("Active engine: "+active+" • Session-specific confirmation rules are active.")
        show=[x for x in ["ticker","session_score","session_state","phase","price","rvol","relative_strength","extension_pct","market_aligned"] if x in qdf]
        def qstyle(row):
            state=str(row.get("session_state",row.get("quality_state","")))
            if "A+" in state:return ["background-color:#123d2a;color:#7CFFB2;font-weight:700" for _ in row]
            if state=="CONFIRMED":return ["background-color:#173653;color:#8ED0FF;font-weight:700" for _ in row]
            if state=="READY":return ["background-color:#44370d;color:#FFE082;font-weight:700" for _ in row]
            return ["" for _ in row]
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Active Engine",active);m2.metric("Candidates",len(qdf));m3.metric("Snapshot",str(s.get("generated_at","—"))[11:19]+" UTC");m4.metric("Mode","PAPER")
        st.markdown("### Top Candidates")
        st.dataframe(qdf[show].style.apply(qstyle,axis=1),use_container_width=True,hide_index=True,height=min(520,72+35*min(len(qdf),12)))
        qt=st.selectbox("Inspect A+ candidate",qdf.ticker.tolist(),key="quality-inspect")
        q=qdf[qdf.ticker==qt].iloc[0]
        k1,k2,k3,k4=st.columns(4)
        k1.metric("Quality",f'{q.get("quality_score",0)}/100');k2.metric("Grade",q.get("grade","—"));k3.metric("State",q.get("quality_state","—"));k4.metric("RS vs SPY",f'{q.get("relative_strength",0)}%')
        checks=q.get("session_checks",q.get("checks",{})); checks=checks if isinstance(checks,dict) else {}
        left,center,right=st.columns([1.05,1.7,1.05])
        with left:
            st.markdown("#### Confirmation checklist")
            for name,ok in checks.items():st.write(("✅" if ok else "❌"),name)
        with center:
            st.markdown("#### Selected Setup")
            st.metric("Ticker",qt)
            st.metric("Session score",str(q.get("session_score",q.get("quality_score",0)))+"/100")
            st.write("State **"+str(q.get("session_state",q.get("quality_state","WATCH")))+"**")
            st.write("Phase **"+str(q.get("phase","—"))+"**")
            st.write("Market aligned **"+("YES" if q.get("market_aligned") else "NO")+"**")
        with right:
            st.markdown("#### Trade Plan")
            st.write(f"Entry **${q.get('entry','—')}** · Stop **${q.get('stop','—')}**")
            st.write(f"1R **${q.get('t1_1r','—')}** · 2R **${q.get('t2_2r','—')}**")
            st.write(f"Shares **{q.get('shares',0)}** · Planned risk **${q.get('planned_risk',0)}**")
            st.write(f"RVOL **{q.get('rvol','—')}x** · Extension **{q.get('extension_pct','—')}%**")
            if not q.get("no_chase",True):st.error("SKIP / WAIT — price is extended more than 0.5% above the ORB trigger.")
            elif q.get("quality_state")=="A+ CONFIRMED":st.success("A+ CONFIRMED — eligible for paper-trade review; not an automatic order.")
            else:st.warning("Not A+ yet — wait for missing confirmations.")
        st.markdown("### Session Statistics")
        z1,z2,z3,z4=st.columns(4)
        z1.metric("Candidates",len(qdf))
        z2.metric("A+ Confirmed",int(qdf["session_state"].astype(str).str.contains("A+",regex=False).sum()) if "session_state" in qdf else 0)
        z3.metric("Ready",int((qdf["session_state"]=="READY").sum()) if "session_state" in qdf else 0)
        avg_rvol=float(qdf["rvol"].fillna(0).mean()) if "rvol" in qdf else 0
        z4.metric("Avg RVOL",format(avg_rvol,".2f")+"x")
        vals=[{"check":k,"value":100 if v else 0} for k,v in checks.items()]
        if vals:
            vf=pd.DataFrame(vals)
            fig=go.Figure(go.Bar(x=vf["value"],y=vf["check"],orientation="h"))
            fig.update_layout(height=390,xaxis=dict(range=[0,100],title="Pass"),margin=dict(l=5,r=5,t=20,b=5),paper_bgcolor="#0d1b2d",plot_bgcolor="#0d1b2d",font_color="#cbd7e6")
            st.plotly_chart(fig,use_container_width=True)

with swing:setups(s.get("swing",[]),"Top 50 Swing Trade Setups")
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
