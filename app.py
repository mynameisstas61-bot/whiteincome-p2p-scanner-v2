import asyncio
import os
from typing import Any
import ccxt.async_support as ccxt
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="WHITEINCOME Scanner API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, restrict to your GitHub Pages origin.
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

EXCHANGE_IDS = {"binance", "bybit", "okx", "kucoin", "mexc", "gate", "bingx"}
ASSET_BASES = {"BTC", "ETH", "SOL"}
DEFAULT_TAKER_FEE = 0.001  # rough estimate: 0.1% per side; configure per venue before relying on results
TIMEOUT_MS = 9000

class ScanRequest(BaseModel):
    deposit: float = Field(default=1000, gt=0, le=1_000_000_000)
    min_spread_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    assets: list[str] = ["USDT", "BTC", "ETH", "SOL"]
    exchanges: list[str] = ["binance", "bybit", "okx", "kucoin", "mexc", "gateio", "bingx"]

def make_exchange(exchange_id: str):
    cls = getattr(ccxt, exchange_id, None)
    if cls is None:
        raise ValueError(f"Unsupported exchange: {exchange_id}")
    return cls({"enableRateLimit": True, "timeout": TIMEOUT_MS, "options": {"defaultType": "spot"}})

async def fetch_market(exchange_id: str, symbol: str) -> dict[str, Any] | None:
    exchange = make_exchange(exchange_id)
    try:
        await exchange.load_markets()
        if symbol not in exchange.markets:
            return None
        ob = await exchange.fetch_order_book(symbol, limit=5)
        asks = ob.get("asks") or []
        bids = ob.get("bids") or []
        if not asks or not bids:
            return None
        return {
            "exchange": exchange_id,
            "symbol": symbol,
            "ask": float(asks[0][0]),
            "ask_amount": float(asks[0][1]),
            "bid": float(bids[0][0]),
            "bid_amount": float(bids[0][1]),
            "timestamp": ob.get("timestamp"),
        }
    except Exception:
        return None
    finally:
        await exchange.close()

@app.get("/health")
async def health():
    return {"ok": True, "service": "WHITEINCOME Scanner API"}

@app.get("/api/opportunities")
async def opportunities(
    deposit: float = Query(1000, gt=0, le=1_000_000_000),
    min_spread_pct: float = Query(5.0, ge=0.0, le=100.0),
    assets: str = Query("USDT,BTC,ETH,SOL"),
    exchanges: str = Query("binance,bybit,okx,kucoin,mexc,gate,bingx"),
    selected_exchanges = [x.strip().lower() for x in exchanges.split(",") if x.strip() in EXCHANGE_IDS]
    selected_assets = [x.strip().upper() for x in assets.split(",") if x.strip()]
    if len(selected_exchanges) < 2:
        return {"opportunities": [], "warnings": ["Выберите минимум две биржи."]}
    # This first version compares crypto/USDT spot markets. USDT itself is the quote currency,
    # so it is not treated as a base asset.
    symbols = [f"{asset}/USDT" for asset in selected_assets if asset in ASSET_BASES]
    if not symbols:
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    jobs = [fetch_market(ex, sym) for ex in selected_exchanges for sym in symbols]
    rows = await asyncio.gather(*jobs, return_exceptions=True)
    rows = [row for row in rows if isinstance(row, dict)]
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row:
            by_symbol.setdefault(row["symbol"], []).append(row)

    found = []
    warnings = [
        "Предварительный спред: комиссии вывода/сети и задержки перевода не включены.",
        "Taker-комиссия оценена как 0.1% на каждую сторону; реальные тарифы бирж отличаются.",
        "Проверяйте доступность актива и одной и той же сети ввода/вывода перед переводом.",
    ]
    for symbol, markets in by_symbol.items():
        for buy in markets:
            for sell in markets:
                if buy["exchange"] == sell["exchange"]:
                    continue
                buy_price = buy["ask"]
                sell_price = sell["bid"]
                gross_pct = (sell_price / buy_price - 1) * 100
                net_pct = ((sell_price * (1 - DEFAULT_TAKER_FEE)) /
                           (buy_price * (1 + DEFAULT_TAKER_FEE)) - 1) * 100
                if net_pct < min_spread_pct:
                    continue
                # A rough capital-limited estimate, bounded by top-of-book amounts.
                quote_budget = deposit
                buy_qty = min(quote_budget / (buy_price * (1 + DEFAULT_TAKER_FEE)),
                              buy["ask_amount"], sell["bid_amount"])
                cost = buy_qty * buy_price * (1 + DEFAULT_TAKER_FEE)
                proceeds = buy_qty * sell_price * (1 - DEFAULT_TAKER_FEE)
                profit = proceeds - cost
                found.append({
                    "symbol": symbol,
                    "buy_exchange": buy["exchange"],
                    "sell_exchange": sell["exchange"],
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "gross_spread_pct": round(gross_pct, 4),
                    "estimated_net_pct_before_transfer_costs": round(net_pct, 4),
                    "estimated_profit_usdt_before_transfer_costs": round(profit, 4),
                    "estimated_size_base": round(buy_qty, 8),
                    "top_ask_amount": buy["ask_amount"],
                    "top_bid_amount": sell["bid_amount"],
                    "timestamp": max(x for x in [buy.get("timestamp"), sell.get("timestamp")] if x is not None)
                                 if buy.get("timestamp") is not None or sell.get("timestamp") is not None else None,
                })
    found.sort(key=lambda x: x["estimated_net_pct_before_transfer_costs"], reverse=True)
    return {"opportunities": found[:100], "warnings": warnings, "checked_markets": len(rows),
            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
