"""
state_manager.py - Global state for the trading bot
"""
from typing import Optional
import json
import os


class StateManager:
    def __init__(self):
        self.bot_status: str = "STOPPED"  # STOPPED | RUNNING | PAUSED
        self.mode: str = "PAPER"          # PAPER | LIVE
        self.active_position: Optional[dict] = None
        self.current_signal: Optional[dict] = None
        self.last_nifty_price: float = 22000.0
        self.atm_ce: Optional[str] = None
        self.atm_pe: Optional[str] = None
        self.candle_buffer: list = []
        self.signal_candle: Optional[dict] = None
        self.prev_signal_candle: Optional[dict] = None
        self.crossover_count: int = 0

        self.settings: dict = {
            # API
            "mstock_api_key": os.getenv("MSTOCK_API_KEY", ""),
            "mstock_api_secret": os.getenv("MSTOCK_API_SECRET", ""),
            "demo_mode": True,

            # Risk
            "quantity": 130,
            "max_sl_points": 20,
            "min_sl_points": 5,
            "rr_trail_unit": 1,

            # Timing
            "entry_start": "09:25",
            "entry_end": "15:00",
            "exit_all_time": "15:10",
            "pre_exit_candle_time": "14:55",

            # VWAP
            "vwap_exit_enabled": True,
            "vwap_signal_filter": True,

            # Paper trading
            "paper_capital": 500000,
            "paper_slippage": 1,

            # Expiry
            "monday_tuesday_next_week": True,
        }

    def reset(self):
        self.active_position = None
        self.current_signal = None
        self.signal_candle = None
        self.prev_signal_candle = None
        self.crossover_count = 0
