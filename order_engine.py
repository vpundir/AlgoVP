"""
order_engine.py - Handles order placement in LIVE and PAPER modes
"""
from datetime import datetime
import httpx


class OrderEngine:
    def __init__(self, state):
        self.state = state
        self._trade_id_counter = 0

    def try_entry(self, signal: dict, mode: str) -> dict | None:
        """Attempt to enter a trade based on signal."""
        if not signal or self.state.active_position:
            return None

        self._trade_id_counter += 1
        entry = {
            "trade_id": self._trade_id_counter,
            "symbol": "NIFTY ATM CE",
            "mode": mode,
            "entry_price": signal["buy_price"],
            "initial_sl": signal["initial_sl"],
            "current_sl": signal["initial_sl"],
            "signal_high": signal["signal_high"],
            "signal_low": signal["signal_low"],
            "quantity": self.state.settings.get("quantity", 130),
            "time_of_entry": datetime.now().isoformat(),
        }

        if mode == "LIVE":
            success = self._place_live_order(entry)
            if not success:
                return None
        # Paper: just track virtually

        return entry

    def _place_live_order(self, entry: dict) -> bool:
        """Place order via M.Stock API."""
        try:
            api_key = self.state.settings.get("mstock_api_key")
            # M.Stock GTT order placement
            import httpx
            with httpx.Client() as client:
                resp = client.post(
                    "https://api.mstock.trade/v1/gtt",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "symbol": entry["symbol"],
                        "quantity": entry["quantity"],
                        "price": entry["entry_price"],
                        "trigger_price": entry["entry_price"],
                        "order_type": "BUY",
                        "sl": entry["initial_sl"],
                    },
                    timeout=5
                )
                return resp.status_code == 200
        except Exception as e:
            print(f"Order placement error: {e}")
            return False

    def execute_exit(self, position: dict, reason: str, mode: str) -> dict:
        """Execute exit order."""
        exit_price = self.state.last_nifty_price  # use LTP
        if mode == "PAPER":
            slippage = self.state.settings.get("paper_slippage", 1)
            exit_price = exit_price - slippage

        pnl = (exit_price - position["entry_price"]) * position["quantity"]

        return {
            "trade_id": position["trade_id"],
            "exit_price": round(exit_price, 2),
            "time_of_exit": datetime.now().isoformat(),
            "reason": reason,
            "pnl": round(pnl, 2),
        }
