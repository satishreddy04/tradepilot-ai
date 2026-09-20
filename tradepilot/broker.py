from .config import settings

def _client():
    if not settings.alpaca_key or not settings.alpaca_secret:
        return None
    from alpaca.trading.client import TradingClient
    return TradingClient(settings.alpaca_key, settings.alpaca_secret, paper=True)

def account_snapshot():
    c=_client()
    if c is None:
        return None
    a=c.get_account()
    return {"equity": float(a.equity), "buying_power": float(a.buying_power), "cash": float(a.cash)}

def positions():
    c=_client()
    if c is None:
        return []
    return [{"symbol":p.symbol,"qty":float(p.qty),"avg_entry_price":float(p.avg_entry_price),"market_value":float(p.market_value),"unrealized_pl":float(p.unrealized_pl)} for p in c.get_all_positions()]

def submit_paper_bracket(symbol: str, qty: int, entry: float, stop: float, target: float):
    c=_client()
    if c is None:
        raise RuntimeError("Alpaca paper credentials are not configured.")
    from alpaca.trading.requests import LimitOrderRequest, TakeProfitRequest, StopLossRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
    req=LimitOrderRequest(
        symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
        limit_price=round(entry,2), order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=round(target,2)),
        stop_loss=StopLossRequest(stop_price=round(stop,2))
    )
    o=c.submit_order(order_data=req)
    return {"id":str(o.id),"symbol":o.symbol,"status":str(o.status)}
