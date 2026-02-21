"""
exit_engine.py - All exit conditions
"""
from datetime import datetime, time
from data_engine import DataEngine


class ExitEngine:
    def __init__(self, state):
        self.state = state
        self._prev_candle: dict | None = None
        self._shooting_star_candle: dict | None = None

    def check_exit(self, position: dict, candle: dict, tick: dict) -> str | None:
        """
        Check all exit conditions. Returns exit reason string or None.
        """
        ltp = tick["ltp"]
        vwap = tick.get("vwap", 0)
        now = datetime.now()
        settings = self.state.settings

        # A. SL Hit
        current_sl = position.get("current_sl", position["initial_sl"])
        if ltp <= current_sl:
            return "SL_HIT"

        # B. Shooting Star Exit
        if self._prev_candle:
            if self._is_shooting_star(self._prev_candle):
                self._shooting_star_candle = self._prev_candle
            if self._shooting_star_candle:
                if candle["low"] < self._shooting_star_candle["low"]:
                    return "SHOOTING_STAR_EXIT"

        # C. Swing Low Exit (simplified: compare with 3-candle swing low)
        swing_low = self._get_swing_low()
        if swing_low and ltp < swing_low:
            return "SWING_LOW_EXIT"

        # D. VWAP Exit
        if settings.get("vwap_exit_enabled") and vwap > 0:
            signal_high = position.get("signal_high", 0)
            # Do NOT exit if green candle hits VWAP above signal_high
            if ltp < vwap:
                if not (candle["close"] > candle["open"] and ltp > signal_high):
                    return "VWAP_EXIT"

        # E. Time-based exits
        exit_all_h, exit_all_m = [int(x) for x in settings["exit_all_time"].split(":")]
        if now.time() >= time(exit_all_h, exit_all_m):
            return "TIME_EXIT_3_10"

        if now.time() >= time(14, 55):
            pre_exit_candle = self._get_2_55_candle()
            if pre_exit_candle and ltp < pre_exit_candle["low"]:
                return "TIME_EXIT_2_55_BREACH"

        self._prev_candle = candle
        return None

    def _is_shooting_star(self, candle: dict) -> bool:
        body = abs(candle["close"] - candle["open"])
        upper_shadow = candle["high"] - max(candle["open"], candle["close"])
        lower_shadow = min(candle["open"], candle["close"]) - candle["low"]
        if body == 0:
            return False
        return upper_shadow >= 3 * body and lower_shadow <= body * 0.2

    def _get_swing_low(self) -> float | None:
        """Get 3-candle swing low from candle history."""
        candles = self.state.candle_buffer
        if len(candles) < 3:
            return None
        lows = [c["low"] for c in candles[-3:]]
        mid_idx = 1
        if lows[mid_idx] < lows[0] and lows[mid_idx] < lows[2]:
            return lows[mid_idx]
        return None

    def _get_2_55_candle(self) -> dict | None:
        """Return the 2:55 PM candle if available."""
        for c in reversed(self.state.candle_buffer or []):
            t = datetime.fromisoformat(c["time"])
            if t.hour == 14 and t.minute == 55:
                return c
        return None
