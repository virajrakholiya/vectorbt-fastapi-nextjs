from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from backend.models import BacktestRequest, BacktestResponse
from backend.fyers_client import DataFetcher
from backend.engine import BacktestEngine, _extract_symbol
from fyers_apiv3 import fyersModel
from dotenv import set_key
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


@app.get("/", response_class=HTMLResponse)
async def handle_fyers_redirect(request: Request):
    auth_code = request.query_params.get("auth_code")
    if not auth_code:
        return """
        <html>
            <body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f4f4f9;">
                <div style="background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;">
                    <h1 style="color: #333;">Fyers Auth Portal</h1>
                    <p style="color: #666;">No auth code found in URL.</p>
                </div>
            </body>
        </html>
        """

    client_id = os.getenv("FYERS_APP_ID")
    secret_key = os.getenv("FYERS_SECRET_KEY")
    redirect_uri = os.getenv("FYERS_REDIRECT_URI")

    try:
        session = fyersModel.SessionModel(
            client_id=client_id,
            secret_key=secret_key,
            redirect_uri=redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )
        session.set_token(auth_code)
        response = session.generate_token()

        if response.get("s") == "ok":
            access_token = response.get("access_token")
            # Update .env
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            set_key(env_path, "FYERS_ACCESS_TOKEN", access_token)
            
            return f"""
            <html>
                <body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #e8f5e9;">
                    <div style="background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 600px; width: 100%;">
                        <h1 style="color: #2e7d32; text-align: center;">Auth Successful!</h1>
                        <p style="color: #333; margin-bottom: 0.5rem;"><strong>Access Token:</strong></p>
                        <textarea readonly style="width: 100%; height: 100px; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; font-size: 0.9rem;">{access_token}</textarea>
                        <p style="color: #666; font-size: 0.9rem; margin-top: 1rem; text-align: center;">The token has been automatically saved to your .env file.</p>
                        <div style="text-align: center; margin-top: 1.5rem;">
                            <button onclick="navigator.clipboard.writeText('{{access_token}}')" style="background: #2e7d32; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 4px; cursor: pointer; font-weight: bold;">Copy Token</button>
                        </div>
                    </div>
                    <script>
                        function copyToClipboard(text) {{
                            navigator.clipboard.writeText(text).then(() => {{
                                alert('Token copied to clipboard!');
                            }});
                        }}
                    </script>
                </body>
            </html>
            """.replace("{{access_token}}", access_token)
        else:
            return f"""
            <html>
                <body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #ffebee;">
                    <div style="background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;">
                        <h1 style="color: #c62828;">Token Generation Failed</h1>
                        <p style="color: #333;">{response.get('message', 'Unknown error')}</p>
                    </div>
                </body>
            </html>
            """
    except Exception as e:
        return f"Error: {str(e)}"


STRATEGY_MAP = {
    "pro_trader": ProTraderStrategy,
    "intraday_scalper": IntradayScalperStrategy,
}

STRATEGY_META = {
    "pro_trader": {
        "label": "Pro Trader (ADX + ATR + Multi-Signal)",
        "description": "Trend follower with EMA stack bias + ADX gate. Four entry triggers: MACD cross, RSI oversold reversal, Donchian breakout, Bollinger lower-band bounce. ATR trailing stop + ATR profit target + EMA trend-break exit. Caps concurrent entries per symbol.",
        "params": [
            {"name": "ema_fast", "label": "EMA Fast", "type": "number", "default": 9, "min": 2, "max": 50},
            {"name": "ema_mid", "label": "EMA Mid", "type": "number", "default": 21, "min": 5, "max": 100},
            {"name": "ema_slow", "label": "EMA Slow", "type": "number", "default": 50, "min": 10, "max": 200},
            {"name": "rsi_window", "label": "RSI Period", "type": "number", "default": 14, "min": 2, "max": 100},
            {"name": "rsi_oversold", "label": "RSI Oversold", "type": "number", "default": 40, "min": 10, "max": 50},
            {"name": "adx_window", "label": "ADX Window", "type": "number", "default": 14, "min": 5, "max": 50},
            {"name": "adx_threshold", "label": "ADX Threshold", "type": "number", "default": 12, "min": 5, "max": 40},
            {"name": "donchian_window", "label": "Donchian Window", "type": "number", "default": 15, "min": 5, "max": 100},
            {"name": "bb_window", "label": "Bollinger Window", "type": "number", "default": 20, "min": 5, "max": 100},
            {"name": "bb_std", "label": "Bollinger Std Dev", "type": "number", "default": 2.0, "min": 1.0, "max": 3.0, "step": 0.1},
            {"name": "atr_window", "label": "ATR Window", "type": "number", "default": 14, "min": 5, "max": 50},
            {"name": "stop_atr_mult", "label": "Stop ATR Mult", "type": "number", "default": 1.5, "min": 0.5, "max": 5.0, "step": 0.1},
            {"name": "target_atr_mult", "label": "Target ATR Mult", "type": "number", "default": 2.8, "min": 1.0, "max": 10.0, "step": 0.1},
            {"name": "macd_fast", "label": "MACD Fast", "type": "number", "default": 12, "min": 3, "max": 50},
            {"name": "macd_slow", "label": "MACD Slow", "type": "number", "default": 26, "min": 10, "max": 100},
            {"name": "macd_signal", "label": "MACD Signal", "type": "number", "default": 9, "min": 3, "max": 30},
            {"name": "max_entries_per_symbol", "label": "Max Entries / Symbol", "type": "number", "default": 2, "min": 1, "max": 5},
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
            intraday_mode=request.intraday_mode,
            leverage=request.leverage,
        )

        portfolio = engine.run(
            entries,
            exits,
            size=getattr(strategy, "entry_size", 1.0),
            accumulate=getattr(strategy, "accumulate", False),
            direction=getattr(strategy, "direction", "long"),
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
                    "time": int(date.timestamp()),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                })
            per_symbol_candles[sym] = candles

        charts["candlesticks"] = per_symbol_candles.get(primary_sym, [])
        charts["per_symbol_candles"] = per_symbol_candles

        # Build per-symbol markers from ORDERS (not trades).
        # With accumulate=True, portfolio.trades groups all pyramid legs into ONE record
        # with the first entry's timestamp, causing all buy arrows to cluster on the same
        # date. portfolio.orders has one row per actual fill with its real timestamp.
        per_symbol_markers = {sym: [] for sym in request.symbols}
        try:
            orders_df = portfolio.orders.records_readable
            # orders_df columns: Timestamp, Column, Side, Price, Size, Fees
            for _, row in orders_df.iterrows():
                sym = _extract_symbol(row.get("Column"), request.symbols)
                if sym not in per_symbol_markers:
                    continue
                ts = row.get("Timestamp")
                price = row.get("Price")
                side = str(row.get("Side", "")).lower()
                if pd.isnull(ts) or pd.isnull(price):
                    continue
                date_str = ts.strftime("%Y-%m-%d")
                if side == "buy":
                    per_symbol_markers[sym].append({
                        "time": date_str,
                        "position": "belowBar",
                        "color": "#22c55e",
                        "shape": "arrowUp",
                        "text": f"Buy @ {float(price):.2f}",
                    })
                elif side == "sell":
                    per_symbol_markers[sym].append({
                        "time": date_str,
                        "position": "aboveBar",
                        "color": "#ef4444",
                        "shape": "arrowDown",
                        "text": f"Sell @ {float(price):.2f}",
                    })
        except Exception:
            # Fallback: use trade records (old behaviour) if orders API unavailable
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
