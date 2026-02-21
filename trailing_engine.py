"""
trailing_engine.py - RR-based trailing stoploss engine
"""


class TrailingEngine:
    def __init__(self, state):
        self.state = state

    def update_trailing_sl(self, position: dict, ltp: float) -> float | None:
        """
        Update SL based on R:R levels.
        R = entry_price - initial_sl
        At 1:1 → move to cost
        At 1:N → move SL to entry + (N-1)*R - 3
        """
        entry = position["entry_price"]
        initial_sl = position["initial_sl"]
        current_sl = position["current_sl"]
        R = entry - initial_sl

        if R <= 0:
            return None

        profit = ltp - entry
        rr = profit / R

        if rr >= 1:
            target_sl = entry  # move to cost at 1:1
        if rr >= 2:
            target_sl = entry + (1 * R) - 3
        if rr >= 3:
            target_sl = entry + (2 * R) - 3
        if rr >= 4:
            target_sl = entry + (3 * R) - 3
        if rr >= 5:
            target_sl = entry + (4 * R) - 3
        else:
            # No trailing needed yet
            if rr < 1:
                return None
            target_sl = entry

        new_sl = round(max(current_sl, target_sl), 2)
        if new_sl > current_sl:
            return new_sl
        return None
