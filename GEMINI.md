# VectorBT Project Instructions

## Trading Skills (Strategies)
The project defines several trading strategies in the `strategies/` directory. These are the "skills" of the trading engine:

### 1. Pro Trader (`ProTraderStrategy`)
- **Type:** Production-grade Multi-Signal strategy.
- **Logic:** Uses a Trends-only filter (ADX + EMA stack) and 4 entry triggers:
  - MACD Cross
  - RSI Reversal
  - Donchian Breakout
  - Bollinger Band Bounce
- **Risk Management:** ATR-adaptive stops with 2.2:1 reward-risk ratio. Supports pyramiding.

### 2. Intraday Scalper (`IntradayScalperStrategy`)
- **Type:** ORB (Opening Range Breakout) + EMA Scalper.
- **Logic:**
  - Bias detection via EMA cross + RSI 50 line.
  - Enters on N-bar high breakout (ORB).
  - Supports pyramiding on continued breakouts.
- **Risk Management:** Tight profit targets and trailing stops. Forced exit at end of day (max hold bars).

## Project Setup & Startup

### Backend (FastAPI)
- **Directory:** `backend/`
- **Virtual Env:** `backend/venv/`
- **Command:** `uvicorn backend.main:app --reload` (run from root)
- **Authentication:** Run `backend/fyers_auth_helper.py` to generate `FYERS_ACCESS_TOKEN`.

### Frontend (Next.js)
- **Directory:** `frontend/`
- **Command:** `npm run dev`

### Unified Startup
- **Command:** `./run.ps1` (Starts both backend and frontend in separate windows).

## Environment Configuration
- `FYERS_APP_ID`, `FYERS_SECRET_KEY`, `FYERS_REDIRECT_URI`, and `FYERS_ACCESS_TOKEN` must be set in `backend/.env`.
