# TradePilot AI

Mobile-friendly Yahoo/yfinance market dashboard for personal testing.

Features: overall bullish/bearish/neutral market regime, Top Day and Swing setups, entry/stop/T1/T2, $5-risk sizing, candlestick inspection, snapshot analytics, Yahoo news/catalysts, optional Telegram confirmed-setup alerts, and GitHub Actions refresh.

Run: `pip install -r requirements.txt`, `python worker.py`, then `streamlit run app.py`.

Telegram: add repository Actions secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; never commit secrets.

Data note: yfinance is unofficial and Yahoo data may be delayed, throttled or unavailable. Confirm actionable prices with your broker. Market regime/scores are rules-based indicators, not forecasts.
