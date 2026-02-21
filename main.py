"""
AlgoTrader Pro - Main FastAPI Application
M.Stock API Integration with Paper Trading Support
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

from state_manager import StateManager
from database import Database, TradeLog
from data_engine import DataEngine
from signal_engine import SignalEngine
from order_engine import OrderEngine
from trailing_engine import TrailingEngine
from exit_engine import ExitEngine
from schemas import (
    BotControlRequest, TradeUpdateRequest, SettingsUpdate,
    TradeResponse, PNLSummary, DailyPNL
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
state = StateManager()
db = Database()
data_engine = DataEngine(state)
signal_engine = SignalEngine(state)
order_engine = OrderEngine(state)
trailing_engine = TrailingEngine(state)
exit_engine = ExitEngine(state)

connected_clients: list[WebSocket] = []


async def broadcast(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)


async def trading_loop():
    """Main trading loop - runs every 5 seconds."""
    while True:
        try:
            if state.bot_status == "RUNNING":
                # Fetch latest candle/tick data
                candle = await data_engine.get_latest_candle()
                tick = await data_engine.get_latest_tick()

                if candle:
                    # Check for signals
                    signal = signal_engine.check_signal(candle)
                    if signal:
                        state.current_signal = signal
                        await broadcast({"type": "signal", "data": signal})
                        logger.info(f"Signal detected: {signal}")

                    # Entry logic
                    if signal and not state.active_position:
                        entry = order_engine.try_entry(signal, state.mode)
                        if entry:
                            state.active_position = entry
                            db.save_trade_entry(entry)
                            await broadcast({"type": "entry", "data": entry})
                            logger.info(f"Entry placed: {entry}")

                    # Trailing SL update
                    if state.active_position and tick:
                        updated_sl = trailing_engine.update_trailing_sl(
                            state.active_position, tick["ltp"]
                        )
                        if updated_sl:
                            state.active_position["current_sl"] = updated_sl
                            await broadcast({"type": "sl_update", "data": {"sl": updated_sl}})

                    # Exit logic
                    if state.active_position and tick:
                        exit_signal = exit_engine.check_exit(
                            state.active_position, candle, tick
                        )
                        if exit_signal:
                            exit_data = order_engine.execute_exit(
                                state.active_position, exit_signal, state.mode
                            )
                            db.close_trade(exit_data)
                            state.active_position = None
                            state.current_signal = None
                            await broadcast({"type": "exit", "data": exit_data})
                            logger.info(f"Exit executed: {exit_data}")

                # Broadcast state update
                await broadcast({
                    "type": "state_update",
                    "data": {
                        "bot_status": state.bot_status,
                        "mode": state.mode,
                        "nifty_price": tick["ltp"] if tick else state.last_nifty_price,
                        "active_position": state.active_position,
                        "current_signal": state.current_signal,
                        "atm_ce": state.atm_ce,
                        "atm_pe": state.atm_pe,
                    }
                })

        except Exception as e:
            logger.error(f"Trading loop error: {e}")
            await broadcast({"type": "error", "message": str(e)})

        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db.init_db()
    asyncio.create_task(trading_loop())
    logger.info("AlgoTrader Pro started")
    yield
    # Shutdown
    logger.info("AlgoTrader Pro stopped")


app = FastAPI(
    title="AlgoTrader Pro",
    description="Algorithmic Trading Platform with M.Stock API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")

    # Send initial state
    await websocket.send_json({
        "type": "init",
        "data": {
            "bot_status": state.bot_status,
            "mode": state.mode,
            "settings": state.settings,
            "active_position": state.active_position,
        }
    })

    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            # Handle client messages if needed
            logger.info(f"WS message: {data}")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info("WebSocket client disconnected")


# ─────────────────────────────────────────────
# Bot Control
# ─────────────────────────────────────────────

@app.post("/api/bot/start")
async def start_bot():
    if state.bot_status == "STOPPED":
        await data_engine.initialize()
    state.bot_status = "RUNNING"
    await broadcast({"type": "bot_status", "status": "RUNNING"})
    return {"status": "RUNNING"}


@app.post("/api/bot/pause")
async def pause_bot():
    state.bot_status = "PAUSED"
    await broadcast({"type": "bot_status", "status": "PAUSED"})
    return {"status": "PAUSED"}


@app.post("/api/bot/stop")
async def stop_bot():
    state.bot_status = "STOPPED"
    state.active_position = None
    state.current_signal = None
    await broadcast({"type": "bot_status", "status": "STOPPED"})
    return {"status": "STOPPED"}


@app.post("/api/bot/mode/{mode}")
async def set_mode(mode: str):
    if mode not in ["LIVE", "PAPER"]:
        raise HTTPException(400, "Mode must be LIVE or PAPER")
    state.mode = mode
    await broadcast({"type": "mode_change", "mode": mode})
    return {"mode": mode}


# ─────────────────────────────────────────────
# Trade Logs
# ─────────────────────────────────────────────

@app.get("/api/trades")
def get_trades(
    date_filter: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None
):
    trades = db.get_trades(date_filter=date_filter, month=month, year=year)
    return trades


@app.put("/api/trades/{trade_id}")
def update_trade(trade_id: int, update: TradeUpdateRequest):
    trade = db.update_trade(trade_id, update.dict(exclude_none=True))
    if not trade:
        raise HTTPException(404, "Trade not found")
    return trade


@app.delete("/api/trades/{trade_id}")
def delete_trade(trade_id: int):
    db.delete_trade(trade_id)
    return {"deleted": trade_id}


@app.get("/api/trades/export/csv")
def export_csv(date_filter: Optional[str] = None):
    import csv
    import io
    trades = db.get_trades(date_filter=date_filter)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "time_of_entry", "entry_price", "time_of_exit",
        "exit_price", "reason_of_exit", "pnl", "mode"
    ])
    writer.writeheader()
    writer.writerows(trades)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=trades_{date.today()}.csv"}
    )


# ─────────────────────────────────────────────
# PNL Dashboard
# ─────────────────────────────────────────────

@app.get("/api/pnl/daily")
def get_daily_pnl(month: Optional[int] = None, year: Optional[int] = None):
    return db.get_daily_pnl(month=month, year=year)


@app.get("/api/pnl/monthly")
def get_monthly_pnl(year: Optional[int] = None):
    return db.get_monthly_pnl(year=year)


@app.get("/api/pnl/summary")
def get_pnl_summary():
    return db.get_pnl_summary()


# ─────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    return state.settings


@app.put("/api/settings")
async def update_settings(settings: SettingsUpdate):
    state.settings.update(settings.dict(exclude_none=True))
    await broadcast({"type": "settings_update", "data": state.settings})
    return state.settings


# ─────────────────────────────────────────────
# Market Data
# ─────────────────────────────────────────────

@app.get("/api/market/nifty")
async def get_nifty():
    tick = await data_engine.get_latest_tick()
    return tick or {"ltp": state.last_nifty_price}


@app.get("/api/market/candles")
async def get_candles(limit: int = 50):
    return data_engine.get_candle_history(limit)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
