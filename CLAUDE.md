# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (uv — preferred)
```powershell
# Install deps
uv sync

# Run dev server (from project root)
uv run uvicorn backend.main:app --reload --port 8000

# Refresh Fyers token (run when token expires)
uv run python -m backend.fyers_auth_helper
```

### Frontend
```powershell
cd frontend
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

### Start both
```powershell
.\run.ps1
```

## Architecture

Full-stack quantitative backtesting platform for Indian equities. FastAPI backend + Next.js frontend. Two independent services.

### Backend (`backend/`)

**Data flow:**
1. `main.py` receives `BacktestRequest` (symbols, dates, strategy, capital, timeframe, params)
2. `fyers_client.py::DataFetcher` fetches OHLCV from Fyers API v3; falls back to yfinance if token absent
3. Strategy `generate_signals()` → entry/exit boolean DataFrames
4. `engine.py::BacktestEngine.run()` → `vbt.Portfolio.from_signals()`, returns portfolio object
5. `get_metrics()` / `get_charts()` / `get_trades()` extract results → `BacktestResponse` JSON

**Key engine details (`engine.py`):**
- `_resolve_freq(timeframe)` maps UI timeframe strings to correct pandas freq + `year_freq` for Sharpe annualization. **Don't hardcode `freq="D"`** — intraday uses NSE trading-minute year (94,500 min).
- Fee model is NSE-realistic (STT + exchange + stamp + SEBI + GST + brokerage) differentiated by intraday vs delivery. Constants: `_INTRADAY_FEES_PCT`, `_DELIVERY_FEES_PCT`, etc.
- Drawdown computed from equity curve via `cummax()`, not `portfolio.drawdown()` (avoided API inconsistency).
- Buy/sell markers use `portfolio.orders.records_readable` (not `portfolio.trades`) so pyramid entries get individual timestamps.

**Strategy system (`strategies/`):**
- All strategies extend `BaseStrategy` (`strategies/base.py`)
- Must implement `generate_signals(data) -> (entries_df, exits_df)` — boolean DataFrames with MultiIndex columns `(field, symbol)`
- Use `align_columns()` utility for MultiIndex column alignment
- Register new strategies in `main.py::STRATEGY_MAP`

**Fyers token (`backend/fyers_auth_helper.py`):**
- Run manually when token expires (daily, ~08:00 IST)
- Opens browser → user logs in → captures auth_code from redirect URL → saves `FYERS_ACCESS_TOKEN` to `.env`
- Redirect also captured automatically via `GET /` endpoint in `main.py`

### Frontend (`frontend/`)

Single-page app (`app/page.tsx`) — no routing. Three tabs: Overview (metrics + equity/drawdown charts), Symbols (per-symbol breakdown), Trades (filterable log).

- **Recharts** for equity curve and drawdown (area charts with amber/red fills)
- **lightweight-charts** for candlestick OHLC + buy/sell markers in `components/TradingChart.tsx`
- **Theme:** amber-phosphor terminal (`#000000` background, `#ffb000` accent). CSS vars in `app/globals.css`.
- API calls: plain `fetch()` to `http://localhost:8000/api/*`

### Environment (`backend/.env`)

```
FYERS_APP_ID        # e.g. ABCD1234-100
FYERS_SECRET_KEY
FYERS_REDIRECT_URI
FYERS_ACCESS_TOKEN  # refreshed daily via fyers_auth_helper.py
```
`.env` is gitignored. Never commit credentials.
