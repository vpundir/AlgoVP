# AlgoTrader Pro 🚀

Algorithmic trading bot for Nifty Options using the 21/34 EMA strategy with M.Stock API.

## Quick Setup

### 1. Extract backend files
```bash
python3 setup.py
```

### 2. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
export MSTOCK_API_KEY=your_key_here
export MSTOCK_API_SECRET=your_secret_here
```

### 4. Run the server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Deploy to Render (Free)
This repo includes a `render.yaml` — just connect it to Render.com and it deploys automatically.

## Strategy: 21/34 EMA Crossover
- **Entry**: 2nd EMA crossover, signal_high > VWAP, SL ≤ 20 pts
- **Trailing SL**: R:R based (1:1 → cost, 1:2 → entry+R-3, etc.)
- **Exit**: SL hit / Shooting star / Swing low / VWAP break / 3:10 PM
- **Modes**: Live (M.Stock GTT orders) + Paper (simulated fills)

## Modules
| File | Purpose |
|------|---------|
| `main.py` | FastAPI app + WebSocket server |
| `state_manager.py` | Bot state (START/PAUSE/STOP) |
| `data_engine.py` | OHLC, EMA21/34, VWAP, demo sim |
| `signal_engine.py` | Entry signal detection |
| `order_engine.py` | Live GTT + paper fills |
| `trailing_engine.py` | R:R trailing SL |
| `exit_engine.py` | All exit conditions |
| `database.py` | SQLite trade logs + PNL |
| `schemas.py` | Pydantic models |
