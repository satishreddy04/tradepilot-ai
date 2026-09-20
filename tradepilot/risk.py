from dataclasses import dataclass
from .config import settings

@dataclass
class RiskDecision:
    allowed: bool
    qty: int
    risk_per_share: float
    reason: str

def size_trade(entry: float, stop: float, buying_power: float, daily_pnl: float, open_positions: int) -> RiskDecision:
    risk = round(entry - stop, 4)
    if risk <= 0:
        return RiskDecision(False, 0, risk, "Stop must be below entry for a long trade.")
    if daily_pnl <= -settings.max_daily_loss:
        return RiskDecision(False, 0, risk, "Daily loss limit reached.")
    if open_positions >= settings.max_positions:
        return RiskDecision(False, 0, risk, "Maximum open positions reached.")
    qty_by_risk = int(settings.max_risk / risk)
    qty_by_cash = int(max(0, buying_power) / entry)
    qty = min(qty_by_risk, qty_by_cash)
    if qty < 1:
        return RiskDecision(False, 0, risk, "Position is too large for current risk/cash limits.")
    return RiskDecision(True, qty, risk, "Risk checks passed.")
