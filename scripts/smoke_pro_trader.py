"""
Smoke test for refactored pro_trader strategy.

Runs new defaults against RELIANCE / TCS / INFY 2023-01-01 -> 2026-05-15
and prints headline metrics + per-symbol breakdown + trade count.

Also runs the OLD defaults (regime off, adx=12, stop=1.5, target=2.8) for
A/B comparison.
"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd
from backend.fyers_client import DataFetcher
from backend.engine import BacktestEngine
from strategies.pro_trader import ProTraderStrategy

SYMBOLS = ["RELIANCE", "TCS", "INFY"]
START   = "2023-01-01"
END     = "2026-05-15"
CAPITAL = 50_000.0


def run(params: dict, label: str, df: pd.DataFrame):
    strategy = ProTraderStrategy(data=df, params=params)
    entries, exits = strategy.generate_signals()

    engine = BacktestEngine(
        data=df,
        initial_capital=CAPITAL,
        fees=0.001,
        slippage=0.0005,
        intraday_mode=False,
        leverage=1.0,
    )
    portfolio = engine.run(
        entries, exits,
        size=getattr(strategy, "entry_size", 1.0),
        accumulate=getattr(strategy, "accumulate", False),
    )

    m = engine.get_metrics(portfolio)
    trades = engine.get_trades(portfolio, symbols=SYMBOLS)
    breakdown = engine.get_symbol_breakdown(trades)

    print(f"\n========== {label} ==========")
    print(f"Total trades       : {m.get('total_trades')}")
    print(f"Win rate           : {m.get('win_rate', 0):.2f}%")
    print(f"Net profit         : INR {m.get('net_profit', 0):.2f}")
    print(f"Total return       : {m.get('total_return', 0):.2f}%")
    print(f"Sharpe             : {m.get('sharpe_ratio', 0):.3f}")
    print(f"Max drawdown       : {m.get('max_drawdown', 0):.2f}%")
    print(f"Final value        : INR {m.get('final_value', 0):.2f}")
    print(f"Fees paid          : INR {m.get('fees_paid', 0):.2f}")
    print("Per-symbol:")
    for b in breakdown:
        print(
            f"  {b['symbol']:10s} trades={b['total_trades']:3d} "
            f"win%={b['win_rate']:6.2f}  P&L=INR {b['total_pnl']:9.2f}"
        )


def main():
    fetcher = DataFetcher()
    fetcher.use_fyers = False   # force yfinance for this smoke test
    df = fetcher.fetch_data(
        symbols=SYMBOLS,
        start_date=START,
        end_date=END,
        timeframe="1d",
    )
    if df.empty:
        print("No data returned.")
        return

    # NEW defaults — match generate_signals defaults
    new_defaults = {}

    # OLD-style defaults (pre-refactor behavior approximation)
    old_defaults = {
        "rsi_oversold":      35,
        "adx_threshold":     12,
        "donchian_window":   15,
        "stop_atr_mult":     1.5,
        "target_atr_mult":   2.8,
        "tight_stop_mult":   1.5,
        "profit_lock_atr":   999,
        "max_entries_per_symbol": 2,
        "pyramid_min_atr":   0.0,
        "time_stop_bars":    9999,
        "use_regime_filter": 0,
        "rsi_pullback_max":  0,
    }

    run(old_defaults, "OLD defaults (regime off, no time-stop, no profit-lock)", df)
    run(new_defaults, "NEW defaults (regime ON, time-stop=60, profit-lock=1.5)", df)


if __name__ == "__main__":
    main()
