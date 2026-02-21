"""
schemas.py - Pydantic models for API request/response
"""
from pydantic import BaseModel
from typing import Optional


class BotControlRequest(BaseModel):
    action: str  # start | pause | stop


class TradeUpdateRequest(BaseModel):
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    time_of_entry: Optional[str] = None
    time_of_exit: Optional[str] = None
    reason_of_exit: Optional[str] = None
    quantity: Optional[int] = None


class SettingsUpdate(BaseModel):
    mstock_api_key: Optional[str] = None
    mstock_api_secret: Optional[str] = None
    demo_mode: Optional[bool] = None
    quantity: Optional[int] = None
    max_sl_points: Optional[float] = None
    min_sl_points: Optional[float] = None
    entry_start: Optional[str] = None
    entry_end: Optional[str] = None
    exit_all_time: Optional[str] = None
    vwap_exit_enabled: Optional[bool] = None
    vwap_signal_filter: Optional[bool] = None
    paper_capital: Optional[float] = None
    paper_slippage: Optional[float] = None
    monday_tuesday_next_week: Optional[bool] = None


class TradeResponse(BaseModel):
    id: int
    time_of_entry: str
    entry_price: float
    time_of_exit: Optional[str]
    exit_price: Optional[float]
    reason_of_exit: Optional[str]
    pnl: Optional[float]
    mode: str


class PNLSummary(BaseModel):
    total_trades: int
    total_pnl: float
    wins: int
    losses: int
    win_rate: float
    avg_win: Optional[float]
    avg_loss: Optional[float]
    best_trade: Optional[float]
    worst_trade: Optional[float]
    avg_rr: float


class DailyPNL(BaseModel):
    trade_date: str
    total_pnl: float
    num_trades: int
    wins: int
    losses: int
