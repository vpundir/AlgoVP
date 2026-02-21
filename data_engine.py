"""
data_engine.py - Fetches OHLC data and computes EMA21, EMA34, VWAP
Supports both M.Stock API (live) and demo simulation
"""
import asyncio
import math
import random
from datetime import datetime, timedelta
from typing import Optional, List
import httpx


class DataEngine:
    def __init__(self, state):
        self.state = state
        self.candle_history: List[dict] = []
        self.ema21: float = 0
        self.ema34: float = 0
        self.vwap: float = 0
        self.cum_vol: float = 0
        self.cum_tp_vol: float = 0
        self._simulated_price: float = 22000.0
        self._sim_tick: int = 0

    async def initialize(self):
        """Fetch ATM strike and initial data."""
        if self.state.settings.get("demo_mode"):
            self._init_demo_candles()
            self._update_atm()
        else:
            await self._fetch_live_atm()

    def _init_demo_candles(self):
        """Generate synthetic historical candles for demo."""
        now = datetime.now().replace(second=0, microsecond=0)
        base_price = 22000 + random.uniform(-200, 200)
        self.candle_history = []
        for i in range(50):
            ts = now - timedelta(minutes=(50 - i) * 5)
            o = base_price + random.uniform(-15, 15)
            h = o + random.uniform(0, 30)
            l = o - random.uniform(0, 20)
            c = random.uniform(l, h)
            v = random.randint(5000, 20000)
            candle = {
                "time": ts.isoformat(),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": v,
            }
            self.candle_history.append(candle)
            base_price = c
            self._update_indicators(candle)
        self._simulated_price = base_price

    def _update_atm(self):
        """Compute ATM CE and PE from current Nifty price."""
        price = self.state.last_nifty_price
        atm = round(price / 50) * 50
        weekday = datetime.now().weekday()  # 0=Mon, 1=Tue
        if weekday in (0, 1) and self.state.settings.get("monday_tuesday_next_week"):
            expiry_label = "next week"
        else:
            expiry_label = "this week"
        self.state.atm_ce = f"NIFTY {atm} CE ({expiry_label})"
        self.state.atm_pe = f"NIFTY {atm} PE ({expiry_label})"

    def _update_indicators(self, candle: dict):
        """Update EMA21, EMA34, VWAP incrementally."""
        c = candle["close"]
        tp = (candle["high"] + candle["low"] + candle["close"]) / 3
        v = candle.get("volume", 1000)

        k21 = 2 / (21 + 1)
        k34 = 2 / (34 + 1)

        if self.ema21 == 0:
            self.ema21 = c
        else:
            self.ema21 = c * k21 + self.ema21 * (1 - k21)

        if self.ema34 == 0:
            self.ema34 = c
        else:
            self.ema34 = c * k34 + self.ema34 * (1 - k34)

        self.cum_vol += v
        self.cum_tp_vol += tp * v
        self.vwap = self.cum_tp_vol / self.cum_vol if self.cum_vol > 0 else c

        candle["ema21"] = round(self.ema21, 2)
        candle["ema34"] = round(self.ema34, 2)
        candle["vwap"] = round(self.vwap, 2)

    async def get_latest_candle(self) -> Optional[dict]:
        """Get the most recently closed 5-min candle."""
        if self.state.settings.get("demo_mode"):
            return await self._get_demo_candle()
        else:
            return await self._fetch_live_candle()

    async def _get_demo_candle(self) -> Optional[dict]:
        """Generate a new synthetic candle periodically."""
        self._sim_tick += 1
        # New candle every 12 ticks (60 sec / 5 sec loop)
        if self._sim_tick % 12 != 0:
            return self.candle_history[-1] if self.candle_history else None

        prev_close = self._simulated_price
        trend = 1 if random.random() > 0.45 else -1
        o = prev_close + random.uniform(-5, 5)
        move = random.uniform(5, 40) * trend
        c = o + move
        h = max(o, c) + random.uniform(0, 15)
        l = min(o, c) - random.uniform(0, 15)
        v = random.randint(5000, 25000)

        candle = {
            "time": datetime.now().isoformat(),
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": v,
        }
        self._update_indicators(candle)
        self.candle_history.append(candle)
        if len(self.candle_history) > 200:
            self.candle_history.pop(0)

        self._simulated_price = c
        self.state.last_nifty_price = c
        self._update_atm()
        return candle

    async def _fetch_live_candle(self) -> Optional[dict]:
        """Fetch 5-min candle from M.Stock API."""
        try:
            api_key = self.state.settings.get("mstock_api_key")
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.mstock.trade/v1/candles",
                    headers=headers,
                    params={"symbol": "NIFTY", "interval": "5"},
                    timeout=5
                )
                data = resp.json()
                candle = data.get("data", {})
                if candle:
                    self._update_indicators(candle)
                    self.candle_history.append(candle)
                    return candle
        except Exception as e:
            print(f"Live candle fetch error: {e}")
        return None

    async def _fetch_live_atm(self):
        """Fetch Nifty price and compute ATM from M.Stock API."""
        try:
            api_key = self.state.settings.get("mstock_api_key")
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.mstock.trade/v1/quote",
                    headers=headers,
                    params={"symbol": "NIFTY 50"},
                    timeout=5
                )
                data = resp.json()
                self.state.last_nifty_price = data.get("ltp", 22000)
                self._update_atm()
        except Exception as e:
            print(f"Live ATM fetch error: {e}")
            self._update_atm()

    async def get_latest_tick(self) -> Optional[dict]:
        """Get latest tick / LTP."""
        if self.state.settings.get("demo_mode"):
            # Simulate small price movement
            drift = random.uniform(-3, 3)
            self._simulated_price += drift
            self.state.last_nifty_price = round(self._simulated_price, 2)
            return {"ltp": self.state.last_nifty_price, "vwap": round(self.vwap, 2)}
        else:
            return await self._fetch_live_tick()

    async def _fetch_live_tick(self) -> Optional[dict]:
        try:
            api_key = self.state.settings.get("mstock_api_key")
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.mstock.trade/v1/ltp",
                    headers=headers,
                    params={"symbol": "NIFTY 50"},
                    timeout=3
                )
                data = resp.json()
                ltp = data.get("ltp", self.state.last_nifty_price)
                self.state.last_nifty_price = ltp
                return {"ltp": ltp, "vwap": round(self.vwap, 2)}
        except Exception as e:
            print(f"Tick fetch error: {e}")
            return {"ltp": self.state.last_nifty_price, "vwap": round(self.vwap, 2)}

    def get_candle_history(self, limit: int = 50) -> List[dict]:
        return self.candle_history[-limit:]

    def detect_shooting_star(self, candle: dict) -> bool:
        """Detect shooting star candlestick pattern."""
        body = abs(candle["close"] - candle["open"])
        upper_shadow = candle["high"] - max(candle["open"], candle["close"])
        lower_shadow = min(candle["open"], candle["close"]) - candle["low"]
        if body == 0:
            return False
        return upper_shadow >= 3 * body and lower_shadow <= body * 0.2
