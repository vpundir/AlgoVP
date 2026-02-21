"""
signal_engine.py - Implements all entry signal logic
21/34 EMA crossover with VWAP, time filters, replacement signal candle
"""
from datetime import datetime, time
from typing import Optional


class SignalEngine:
    def __init__(self, state):
        self.state = state
        self.prev_above_both: bool = False
        self.crossover_history: list = []  # track crossover events

    def check_signal(self, candle: dict) -> Optional[dict]:
        """
        Main signal detection. Returns signal dict or None.
        """
        now = datetime.fromisoformat(candle["time"])
        settings = self.state.settings

        # ── Time filters ──
        entry_start = time(9, 25)
        entry_end_h, entry_end_m = [int(x) for x in settings["entry_end"].split(":")]
        entry_end = time(entry_end_h, entry_end_m)

        current_time = now.time()
        if current_time < entry_start or current_time > entry_end:
            return None

        # ── EMA crossover check ──
        ema21 = candle.get("ema21", 0)
        ema34 = candle.get("ema34", 0)
        close = candle["close"]

        above_both = close > ema21 and close > ema34

        if above_both and not self.prev_above_both:
            # New crossover event
            self.crossover_history.append({
                "candle": candle,
                "count": len(self.crossover_history) + 1
            })

        self.prev_above_both = above_both

        # ── Need SECOND crossover ──
        if len(self.crossover_history) < 2:
            return None

        # ── Signal candle is the most recent crossover candle ──
        signal_candle = self.crossover_history[-1]["candle"]
        signal_high = signal_candle["high"]
        signal_low = signal_candle["low"]

        # ── VWAP condition: signal_high must be > VWAP ──
        vwap = candle.get("vwap", 0)
        if self.state.settings.get("vwap_signal_filter") and signal_high <= vwap:
            return None

        # ── Replacement signal candle rule ──
        # If no position and a new signal appears with LOWER high, replace
        if self.state.signal_candle:
            prev_sh = self.state.signal_candle.get("signal_high", float("inf"))
            if not self.state.active_position and signal_high < prev_sh:
                # Replace with new lower signal candle
                self.state.signal_candle = {
                    "signal_high": signal_high,
                    "signal_low": signal_low,
                    "candle_time": signal_candle["time"],
                }
                return None  # Not yet triggered

        # ── Check if price broke above signal_high ──
        if self.state.signal_candle:
            trigger_price = self.state.signal_candle["signal_high"] + 2
            if candle["close"] >= trigger_price and not self.state.active_position:
                signal = self._build_signal(self.state.signal_candle, candle, vwap)
                return signal
        else:
            # Store as signal candle
            self.state.signal_candle = {
                "signal_high": signal_high,
                "signal_low": signal_low,
                "candle_time": signal_candle["time"],
            }

        return None

    def _build_signal(self, signal_candle: dict, trigger_candle: dict, vwap: float) -> dict:
        signal_high = signal_candle["signal_high"]
        signal_low = signal_candle["signal_low"]

        buy_price = signal_high + 2
        sl_candidate_1 = signal_low - 1
        sl_candidate_2 = buy_price - 20  # min 20 points SL
        initial_sl = max(sl_candidate_1, sl_candidate_2)  # use the one closer to price

        sl_distance = buy_price - initial_sl

        if sl_distance > 20:
            return None  # Reject

        return {
            "type": "CE_BUY",
            "signal_high": signal_high,
            "signal_low": signal_low,
            "buy_price": round(buy_price, 2),
            "initial_sl": round(initial_sl, 2),
            "sl_distance": round(sl_distance, 2),
            "vwap": round(vwap, 2),
            "trigger_candle_time": trigger_candle["time"],
            "signal_candle_time": signal_candle["candle_time"],
            "ema21": trigger_candle.get("ema21"),
            "ema34": trigger_candle.get("ema34"),
        }

    def reset(self):
        self.prev_above_both = False
        self.crossover_history = []
