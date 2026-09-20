import requests
from .config import settings

def send_telegram(message: str) -> bool:
    if not settings.telegram_token or not settings.telegram_chat_id:
        return False
    url = "https://api.telegram.org/bot" + settings.telegram_token + "/sendMessage"
    r = requests.post(url, json={"chat_id": settings.telegram_chat_id, "text": message}, timeout=10)
    r.raise_for_status()
    return True
