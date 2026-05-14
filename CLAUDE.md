# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
# Run from project root:
uvicorn backend.main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

### Start both together
```powershell
.\run.ps1
```

### Fyers API auth (one-time setup)
```powershell
cd backend && python fyers_auth_helper.py
```

## Architecture

Full-stack backtesting platform for Indian equities. FastAPI backend + Next.js frontend. Two services, no shared process.

### Backend (`backend/`)

**Entry:** `main.py` — FastAPI app, CORS open, two routes:
- `POST /api/backtest` → runs strategy, returns metrics + chart data + trades
- `GET /api/strategies` → lists available strategies with parameter metadata

**Data flow:**
1. `main.py` receives `BacktestRequest` (symbols, dates, strategy, capital, params)
2. `fyers_client.py::DataFetcher` fetches OHLCV from Fyers API v3 (or yfinance fallback), returns MultiIndex DataFrame
3. Strategy `generate_signals()` produces entry/exit boolean DataFrames
4. `engine.py::BacktestEngine` runs VectorBT `vbt.Portfolio.from_signals()`, computes metrics/charts/trades
5. Returns `BacktestResponse` JSON

**Strategy system (`strategies/`):**
- All strategies extend `BaseStrategy` (abstract, in `strategies/base.py`)
- Must implement `generate_signals(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]` (entries, exits)
- `accumulate` property enables pyramiding; `entry_size` controls position sizing
- `align_columns()` utility handles VectorBT's MultiIndex column structure
- Registered in `main.py::STRATEGY_MAP` dict — add new strategies there

**Key VectorBT pattern:** signals are boolean DataFrames with MultiIndex columns `(field, symbol)`. Always use `align_columns()` when building signals to match this structure.

### Frontend (`frontend/`)

Single-page app (`app/page.tsx`) — no routing beyond root. Three tabs: Overview (metrics cards), Symbols (per-symbol breakdown), Trades (trade log with filters).

**Charting:** Recharts for equity/drawdown curves; `lightweight-charts` for candlestick OHLC in `components/TradingChart.tsx`.

**API calls:** Plain `fetch()` to `http://localhost:8000/api/*`, no client library.

### Environment

Backend reads `backend/.env` for Fyers credentials:
```
FYERS_CLIENT_ID=...
FYERS_ACCESS_TOKEN=...
```
Missing `.env` → falls back to yfinance automatically.
