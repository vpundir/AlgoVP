"""
database.py - SQLite database for trade logs and PNL
"""
import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict
from dataclasses import dataclass


DB_PATH = "trading.db"


@dataclass
class TradeLog:
    id: int
    time_of_entry: str
    entry_price: float
    time_of_exit: Optional[str]
    exit_price: Optional[float]
    reason_of_exit: Optional[str]
    pnl: Optional[float]
    mode: str
    quantity: int
    symbol: str


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL DEFAULT 'NIFTY',
                    mode TEXT NOT NULL DEFAULT 'PAPER',
                    time_of_entry TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    time_of_exit TEXT,
                    exit_price REAL,
                    reason_of_exit TEXT,
                    pnl REAL,
                    quantity INTEGER DEFAULT 130,
                    initial_sl REAL,
                    signal_high REAL,
                    signal_low REAL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def save_trade_entry(self, entry: dict) -> int:
        with self.get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO trades (symbol, mode, time_of_entry, entry_price, quantity,
                                   initial_sl, signal_high, signal_low)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get("symbol", "NIFTY"),
                entry.get("mode", "PAPER"),
                entry.get("time_of_entry", datetime.now().isoformat()),
                entry["entry_price"],
                entry.get("quantity", 130),
                entry.get("initial_sl"),
                entry.get("signal_high"),
                entry.get("signal_low"),
            ))
            conn.commit()
            return cur.lastrowid

    def close_trade(self, exit_data: dict):
        with self.get_conn() as conn:
            # Calculate PNL
            trade_id = exit_data.get("trade_id")
            row = conn.execute("SELECT entry_price, quantity FROM trades WHERE id=?", (trade_id,)).fetchone()
            if row:
                pnl = (exit_data["exit_price"] - row["entry_price"]) * row["quantity"]
                conn.execute("""
                    UPDATE trades
                    SET time_of_exit=?, exit_price=?, reason_of_exit=?, pnl=?
                    WHERE id=?
                """, (
                    exit_data.get("time_of_exit", datetime.now().isoformat()),
                    exit_data["exit_price"],
                    exit_data.get("reason", "MANUAL"),
                    pnl,
                    trade_id,
                ))
                conn.commit()

    def get_trades(self, date_filter: Optional[str] = None,
                   month: Optional[int] = None,
                   year: Optional[int] = None) -> List[dict]:
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if date_filter:
            query += " AND DATE(time_of_entry) = ?"
            params.append(date_filter)
        if month:
            query += " AND strftime('%m', time_of_entry) = ?"
            params.append(f"{month:02d}")
        if year:
            query += " AND strftime('%Y', time_of_entry) = ?"
            params.append(str(year))

        query += " ORDER BY time_of_entry DESC"

        with self.get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update_trade(self, trade_id: int, updates: dict) -> Optional[dict]:
        allowed = {"entry_price", "exit_price", "time_of_entry",
                   "time_of_exit", "reason_of_exit", "quantity"}
        safe_updates = {k: v for k, v in updates.items() if k in allowed}

        if not safe_updates:
            return None

        with self.get_conn() as conn:
            # Recalculate PNL if prices changed
            row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            if not row:
                return None

            entry_price = safe_updates.get("entry_price", row["entry_price"])
            exit_price = safe_updates.get("exit_price", row["exit_price"])
            quantity = safe_updates.get("quantity", row["quantity"])

            if exit_price:
                pnl = (float(exit_price) - float(entry_price)) * int(quantity)
                safe_updates["pnl"] = pnl

            set_clause = ", ".join(f"{k}=?" for k in safe_updates)
            values = list(safe_updates.values()) + [trade_id]
            conn.execute(f"UPDATE trades SET {set_clause} WHERE id=?", values)
            conn.commit()

            updated = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            return dict(updated) if updated else None

    def delete_trade(self, trade_id: int):
        with self.get_conn() as conn:
            conn.execute("DELETE FROM trades WHERE id=?", (trade_id,))
            conn.commit()

    def get_daily_pnl(self, month: Optional[int] = None, year: Optional[int] = None) -> List[dict]:
        query = """
            SELECT DATE(time_of_entry) as trade_date,
                   SUM(pnl) as total_pnl,
                   COUNT(*) as num_trades,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses
            FROM trades
            WHERE pnl IS NOT NULL
        """
        params = []
        if month:
            query += " AND strftime('%m', time_of_entry) = ?"
            params.append(f"{month:02d}")
        if year:
            query += " AND strftime('%Y', time_of_entry) = ?"
            params.append(str(year))
        query += " GROUP BY DATE(time_of_entry) ORDER BY trade_date DESC"

        with self.get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_monthly_pnl(self, year: Optional[int] = None) -> List[dict]:
        query = """
            SELECT strftime('%Y-%m', time_of_entry) as month,
                   SUM(pnl) as total_pnl,
                   COUNT(*) as num_trades,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
            FROM trades
            WHERE pnl IS NOT NULL
        """
        params = []
        if year:
            query += " AND strftime('%Y', time_of_entry) = ?"
            params.append(str(year))
        query += " GROUP BY strftime('%Y-%m', time_of_entry) ORDER BY month DESC"

        with self.get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_pnl_summary(self) -> dict:
        with self.get_conn() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(pnl) as total_pnl,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                    AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                    AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM trades WHERE pnl IS NOT NULL
            """).fetchone()

            data = dict(row)
            total = data["total_trades"] or 0
            wins = data["wins"] or 0
            data["win_rate"] = round((wins / total * 100), 2) if total > 0 else 0
            data["avg_rr"] = round(
                abs((data["avg_win"] or 0) / (data["avg_loss"] or 1)), 2
            )
            return data
