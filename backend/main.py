from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.models import BacktestRequest, BacktestResponse
from backend.fyers_client import DataFetcher
from backend.engine import BacktestEngine
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.sma_crossover import SMACrossoverStrategy
from strategies.sma_rsi import SMARSIStrategy

app = FastAPI(title="VectorBT Backtesting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_fetcher = DataFetcher()

STRATEGY_MAP = {
    "sma_crossover": SMACrossoverStrategy,
    "sma_rsi": SMARSIStrategy,
}

STRATEGY_META = {
    "sma_crossover": {
        "label": "SMA Crossover",
        "description": "Classic moving-average crossover.",
        "params": [
            {"name": "fast_window", "label": "Fast SMA", "type": "number", "default": 10, "min": 2, "max": 200},
            {"name": "slow_window", "label": "Slow SMA", "type": "number", "default": 50, "min": 5, "max": 400},
        ],
    },
    "sma_rsi": {
        "label": "SMA + RSI + Trailing Stop",
        "description": "SMA crossover with RSI confirmation and trailing stop loss for accuracy.",
        "params": [
            {"name": "fast_window", "label": "Fast SMA", "type": "number", "default": 20, "min": 2, "max": 200},
            {"name": "slow_window", "label": "Slow SMA", "type": "number", "default": 50, "min": 5, "max": 400},
            {"name": "rsi_window", "label": "RSI Period", "type": "number", "default": 14, "min": 2, "max": 100},
            {"name": "rsi_overbought", "label": "RSI Overbought", "type": "number", "default": 70, "min": 50, "max": 95},
            {"name": "rsi_oversold", "label": "RSI Oversold", "type": "number", "default": 30, "min": 5, "max": 50},
            {"name": "stop_loss_pct", "label": "Trailing Stop %", "type": "number", "default": 0.05, "min": 0.005, "max": 0.5, "step": 0.005},
        ],
    },
}


@app.post("/api/backtest", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    try:
        if request.strategy_name not in STRATEGY_MAP:
            raise HTTPException(status_code=400, detail="Strategy not found")

        df = data_fetcher.fetch_data(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe,
        )

        if df.empty:
            raise HTTPException(status_code=400, detail="No data returned for given symbols and dates")

        strategy_class = STRATEGY_MAP[request.strategy_name]
        strategy = strategy_class(data=df, params=request.params)
        entries, exits = strategy.generate_signals()

        engine = BacktestEngine(
            data=df,
            initial_capital=request.initial_capital,
            fees=0.001,
            slippage=0.0005,
        )

        portfolio = engine.run(entries, exits, size=1.0)

        metrics = engine.get_metrics(portfolio)
        charts = engine.get_charts(portfolio, symbols=request.symbols)
        trades = engine.get_trades(portfolio, symbols=request.symbols)
        breakdown = engine.get_symbol_breakdown(trades)

        # Per-symbol candlestick data
        primary_sym = request.symbols[0]
        per_symbol_candles = {}

        for sym in request.symbols:
            if isinstance(df.columns, pd.MultiIndex) and sym in df.columns.get_level_values(0):
                sym_df = df[sym]
            elif not isinstance(df.columns, pd.MultiIndex):
                sym_df = df
            else:
                continue

            candles = []
            for date, row in sym_df.iterrows():
                candles.append({
                    "time": date.strftime("%Y-%m-%d"),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                })
            per_symbol_candles[sym] = candles

        charts["candlesticks"] = per_symbol_candles.get(primary_sym, [])
        charts["per_symbol_candles"] = per_symbol_candles

        # Build per-symbol markers
        per_symbol_markers = {sym: [] for sym in request.symbols}
        for t in trades:
            sym = t["symbol"]
            if sym not in per_symbol_markers:
                continue
            if t["entry_date"]:
                per_symbol_markers[sym].append({
                    "time": t["entry_date"],
                    "position": "belowBar",
                    "color": "#22c55e",
                    "shape": "arrowUp",
                    "text": f"Buy @ {t['entry_price']:.2f}" if t["entry_price"] is not None else "Buy",
                })
            if t["exit_date"] and t["exit_price"] is not None:
                per_symbol_markers[sym].append({
                    "time": t["exit_date"],
                    "position": "aboveBar",
                    "color": "#ef4444",
                    "shape": "arrowDown",
                    "text": f"Sell @ {t['exit_price']:.2f}",
                })

        # Sort markers chronologically (lightweight-charts requires sorted markers)
        for sym in per_symbol_markers:
            per_symbol_markers[sym].sort(key=lambda m: m["time"])

        charts["markers"] = per_symbol_markers.get(primary_sym, [])
        charts["per_symbol_markers"] = per_symbol_markers

        # Stash breakdown into metrics dict for easy frontend access
        metrics["symbol_breakdown"] = breakdown

        return BacktestResponse(
            metrics=metrics,
            charts=charts,
            trades=trades,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies")
async def list_strategies():
    return {
        "strategies": [
            {"id": k, **STRATEGY_META[k]}
            for k in STRATEGY_MAP.keys()
        ]
    }
