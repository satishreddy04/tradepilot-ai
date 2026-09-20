import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    alpaca_key: str = os.getenv("ALPACA_API_KEY", "")
    alpaca_secret: str = os.getenv("ALPACA_SECRET_KEY", "")
    paper: bool = os.getenv("ALPACA_PAPER", "true").lower() == "true"
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    max_risk: float = float(os.getenv("MAX_RISK_PER_TRADE", "5"))
    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", "10"))
    max_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", "2"))

settings = Settings()
