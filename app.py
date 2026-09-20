import json
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="TradePilot AI",page_icon="📈",layout="wide")
st.markdown("""<style>.stApp{background:#07111f;color:#e8eef7}.block-container{padding-top:1rem;max-width:1500px}[data-testid="stMetric"]{background:#0d1b2d;border:1px solid #20324a;padding:12px;border-radius:14px}.card{background:#0d1b2d;border:1px solid #20324a;border-radius:16px;padding:15px;margin-bottom:10px}.muted{color:#8ea2bc}</style>""",unsafe_allow_html=True)
p=Path("docs/data/snapshot.json")
try:s=json.loads(p.read_text())
except:s={"generated_at":None,"market":{"label":"WAITING FOR SCAN","score":50},"day":[],"swing":[],"news":[],"analytics":{}}
m=s.get("market",{})
st.title("📈 TradePilot AI")
st.caption("Market regime • Day & swing setups • targets/stops • analytics • news")
c=st.columns(6)
c[0].metric("Market",m.get("label","UNKNOWN"));c[1].metric("Score",str(m.get("score",0))+"/100")
c[2].metric("SPY",m.get("spy",{}).get("price","—"));c[3].metric("QQQ",m.get("qqq",{}).get("price","—"))
c[4].metric("Breadth",(str(m.get("breadth"))+"%") if m.get("breadth") is not None else "—");c[5].metric("Snapshot",s.get("generated_at") or "not built")
st.markdown('<div class="card"><b>Overall Market: '+str(m.get("label","UNKNOWN"))+'</b><br><span class="muted">Rules-based SPY/QQQ EMA structure + watchlist breadth; not a forecast.</span></div>',unsafe_allow_html=True)
def setups(rows,title):
 st.subheader(title)
 if not rows: st.info("Waiting for first Yahoo Finance snapshot.");return
 df=pd.DataFrame(rows); cols=[x for x in ["ticker","price","score","rvol","setup","status","entry","stop","t1","t2","risk_share"] if x in df]
 st.dataframe(df[cols],use_container_width=True,hide_index=True)
 t=st.selectbox("Inspect",df.ticker.tolist(),key=title);r=df[df.ticker==t].iloc[0]
 a,b=st.columns([2,1]);cd=r.get("chart",[])
 if isinstance(cd,list) and cd:
  d=pd.DataFrame(cd);fig=go.Figure(go.Candlestick(x=d.time,open=d.open,high=d.high,low=d.low,close=d.close))
  for k,n in [("entry","Entry"),("stop","Stop"),("t1","T1"),("t2","T2")]:
   if pd.notna(r.get(k)):fig.add_hline(y=float(r[k]),line_dash="dash",annotation_text=n)
  fig.update_layout(height=390,paper_bgcolor="#0d1b2d",plot_bgcolor="#0d1b2d",font_color="#cbd7e6",xaxis_rangeslider_visible=False);a.plotly_chart(fig,use_container_width=True)
 risk=float(r.get("risk_share",0) or 0);shares=int(5/risk) if risk>0 else 0
 b.markdown('<div class="card"><b>'+str(r.ticker)+'</b> · '+str(r.get("status",""))+'<hr>Setup: <b>'+str(r.get("setup",""))+'</b><br>Score: <b>'+str(r.get("score",""))+'/100</b><br>RVOL: <b>'+str(r.get("rvol","—"))+'x</b><hr>Entry: <b>$'+str(r.get("entry","—"))+'</b><br>Stop: <b>$'+str(r.get("stop","—"))+'</b><br>T1: <b>$'+str(r.get("t1","—"))+'</b><br>T2: <b>$'+str(r.get("t2","—"))+'</b><br>Risk/share: <b>$'+format(risk,'.2f')+'</b><br>Max shares @ $5 risk: <b>'+str(shares)+'</b></div>',unsafe_allow_html=True)
day,swing,analytics,news=st.tabs(["⚡ Day Trades","📆 Swing Trades","📊 Analytics","📰 News & Catalysts"])
with day:setups(s.get("day",[]),"Top Day Trade Setups")
with swing:setups(s.get("swing",[]),"Top Swing Trade Setups")
with analytics:
 a=s.get("analytics",{});cc=st.columns(4);cc[0].metric("Bullish watchlist",a.get("bullish_count",0));cc[1].metric("Bearish watchlist",a.get("bearish_count",0));cc[2].metric("Day confirmed",a.get("day_confirmed",0));cc[3].metric("Swing ready+",a.get("swing_ready",0))
with news:
 if not s.get("news"):st.info("No current catalysts in snapshot.")
 for n in s.get("news",[])[:30]:st.markdown('<div class="card"><b>'+str(n.get("ticker","MARKET"))+'</b> — '+str(n.get("title",""))+'<br><span class="muted">'+str(n.get("publisher",""))+' · '+str(n.get("published",""))+'</span><br><a href="'+str(n.get("link","#"))+'" target="_blank">Open source</a></div>',unsafe_allow_html=True)
st.caption("Yahoo/yfinance is unofficial and may be delayed, throttled or unavailable. Confirm prices with your broker before trading.")
