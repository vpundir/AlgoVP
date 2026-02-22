# AlgoTrader Pro

21/34 EMA algo trading bot for Nifty Options with M.Stock API.

## Deploy on Railway
Connect this repo to Railway.app — it auto-detects railway.toml.

## Environment Variables
- MSTOCK_API_KEY
- MSTOCK_API_SECRET

## Run Locally
pip install -r requirements.txt
uvicorn main:app --reload
