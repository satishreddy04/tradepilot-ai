# TradePilot AI

Mobile-friendly day/swing trading dashboard with scanner, alerts, risk sizing, manual controls and paper-auto execution hooks.

## Run
1. python -m venv .venv
2. Activate it
3. pip install -r requirements.txt
4. streamlit run app.py

## Deploy
Deploy this repository on Streamlit Community Cloud and set app.py as the entry file. Add broker/Telegram credentials only through deployment secrets.

## V1 safety
Live-money AUTO execution is intentionally disabled. Validate the scanner and Alpaca paper execution first.
