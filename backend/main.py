from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.models import BacktestRequest, BacktestResponse
from backend.fyers_client import DataFetcher
from backend.engine import BacktestEngine
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.intraday_scalper import IntradayScalperStrategy
from strategies.pro_trader import ProTraderStrategy

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
    "pro_trader": ProTraderStrategy,
    "intraday_scalper": IntradayScalperStrategy,
}

STRATEGY_META = {
    "pro_trader": {
        "label": "Pro Trader (ADX + ATR + Multi-Signal)",
        "description": "Production-grade strategy. Trends-only filter (ADX + EMA stack), 4 entry triggers (MACD cross / RSI reversal / Donchian breakout / BB bounce), ATR-adaptive stops with 2.2:1 reward-risk. Pyramids on continuation. Built for stable + profitable + frequent.",
        "params": [
            {"name": "ema_fast", "label": "EMA Fast", "type": "number", "default": 9, "min": 2, "max": 50},
            {"name": "ema_mid", "label": "EMA Mid", "type": "number", "default": 21, "min": 5, "max": 100},
            {"name": "ema_slow", "label": "EMA Slow", "type": "number", "default": 50, "min": 10, "max": 200},
            {"name": "rsi_window", "label": "RSI Period", "type": "number", "default": 14, "min": 2, "max": 100},
            {"name": "rsi_oversold", "label": "RSI Oversold", "type": "number", "default": 35, "min": 10, "max": 50},
            {"name": "adx_window", "label": "ADX Window", "type": "number", "default": 14, "min": 5, "max": 50},
            {"name": "adx_threshold", "label": "ADX Threshold", "type": "number", "default": 18, "min": 10, "max": 40},
            {"name": "donchian_window", "label": "Donchian Window", "type": "number", "default": 20, "min": 5, "max": 100},
            {"name": "bb_window", "label": "Bollinger Window", "type": "number", "default": 20, "min": 5, "max": 100},
            {"name": "atr_window", "label": "ATR Window", "type": "number", "default": 14, "min": 5, "max": 50},
            {"name": "stop_atr_mult", "label": "Stop ATR Mult", "type": "number", "default": 1.8, "min": 0.5, "max": 5.0, "step": 0.1},
            {"name": "target_atr_mult", "label": "Target ATR Mult", "type": "number", "default": 4.0, "min": 1.0, "max": 10.0, "step": 0.1},
        ],
    },
    "intraday_scalper": {
        "label": "Intraday Scalper (ORB + EMA + Pyramid)",
        "description": "Stock-equivalent of an intraday options scalper. ORB breakout + EMA bias + RSI filter, pyramids on continuation, scalps on tight profit target / trailing stop / max-hold timeout.",
        "params": [
            {"name": "breakout_window", "label": "Breakout Window", "type": "number", "default": 5, "min": 2, "max": 50},
            {"name": "ema_fast", "label": "EMA Fast", "type": "number", "default": 9, "min": 2, "max": 100},
            {"name": "ema_slow", "label": "EMA Slow", "type": "number", "default": 21, "min": 5, "max": 200},
            {"name": "rsi_window", "label": "RSI Period", "type": "number", "default": 14, "min": 2, "max": 100},
            {"name": "rsi_floor", "label": "RSI Floor", "type": "number", "default": 45, "min": 20, "max": 60},
            {"name": "rsi_ceiling", "label": "RSI Ceiling", "type": "number", "default": 75, "min": 60, "max": 95},
            {"name": "max_hold", "label": "Max Hold (bars)", "type": "number", "default": 5, "min": 1, "max": 100},
            {"name": "profit_target", "label": "Profit Target %", "type": "number", "default": 0.03, "min": 0.005, "max": 0.5, "step": 0.005},
            {"name": "stop_loss", "label": "Trailing Stop %", "type": "number", "default": 0.015, "min": 0.005, "max": 0.2, "step": 0.005},
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

        portfolio = engine.run(
            entries,
            exits,
            size=getattr(strategy, "entry_size", 1.0),
            accumulate=getattr(strategy, "accumulate", False),
        )

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
