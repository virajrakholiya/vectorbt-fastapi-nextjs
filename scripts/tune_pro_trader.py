"""
Grid-search pro_trader params on yfinance data 2023-01-01 -> 2026-05-15.

Goal: maximize Sharpe while keeping trades > 30 and DD < 20%.
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


def evaluate(params: dict, df: pd.DataFrame) -> dict:
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
    return {
        "trades": m.get("total_trades", 0),
        "win_rate": m.get("win_rate", 0),
        "net_profit": m.get("net_profit", 0),
        "return": m.get("total_return", 0),
        "sharpe": m.get("sharpe_ratio", 0),
        "dd": m.get("max_drawdown", 0),
    }


def main():
    fetcher = DataFetcher()
    fetcher.use_fyers = False
    df = fetcher.fetch_data(
        symbols=SYMBOLS,
        start_date=START,
        end_date=END,
        timeframe="1d",
    )
    if df.empty:
        print("No data.")
        return

    # Param grid — focus on what matters: regime, profit-lock, stop, target, time-stop
    grid = []
    for use_regime in [0, 1]:
        for adx_th in [12, 15, 20]:
            for stop_mult in [1.5, 1.8, 2.0]:
                for target_mult in [2.8, 3.5, 4.5]:
                    for profit_lock in [999, 2.0, 3.0]:  # 999 effectively disables
                        for time_stop in [60, 90, 9999]:
                            grid.append({
                                "use_regime_filter": use_regime,
                                "adx_threshold":     adx_th,
                                "stop_atr_mult":     stop_mult,
                                "target_atr_mult":   target_mult,
                                "profit_lock_atr":   profit_lock,
                                "tight_stop_mult":   1.0,
                                "time_stop_bars":    time_stop,
                            })

    print(f"Evaluating {len(grid)} configs...")
    results = []
    for i, p in enumerate(grid):
        r = evaluate(p, df)
        r.update(p)
        results.append(r)
        if (i+1) % 50 == 0:
            print(f"  {i+1}/{len(grid)}")

    # Filter: trades >= 30, DD <= 20 (stricter)
    qualified = [r for r in results if r["trades"] >= 30 and r["dd"] <= 20]
    qualified.sort(key=lambda r: r["sharpe"], reverse=True)

    print(f"\n{len(qualified)} configs qualified (trades>=30, DD<=20%)")
    print("\nTop 15 by Sharpe:")
    print(f"{'regime':>6} {'adx':>4} {'stop':>5} {'tgt':>5} {'lock':>5} {'tstop':>5} "
          f"{'trades':>6} {'win%':>6} {'ret%':>7} {'sharpe':>7} {'dd%':>6}")
    for r in qualified[:10]:
        print(
            f"{r['use_regime_filter']:>6} {r['adx_threshold']:>4} "
            f"{r['stop_atr_mult']:>5.1f} {r['target_atr_mult']:>5.1f} "
            f"{r['profit_lock_atr']:>5.1f} {r['time_stop_bars']:>5d} "
            f"{r['trades']:>6d} {r['win_rate']:>6.2f} {r['return']:>7.2f} "
            f"{r['sharpe']:>7.3f} {r['dd']:>6.2f}"
        )

    print("\nTop 10 by Return (any DD):")
    by_ret = sorted(results, key=lambda r: r["return"], reverse=True)
    for r in by_ret[:10]:
        print(
            f"  regime={r['use_regime_filter']} adx={r['adx_threshold']} "
            f"stop={r['stop_atr_mult']} tgt={r['target_atr_mult']} "
            f"lock={r['profit_lock_atr']} tstop={r['time_stop_bars']} "
            f"=> trades={r['trades']} ret={r['return']:.2f}% sharpe={r['sharpe']:.3f} dd={r['dd']:.2f}%"
        )

    print("\nBest balanced (sharpe + low DD, trades>=40):")
    balanced = [r for r in results if r["trades"] >= 40]
    balanced.sort(
        key=lambda r: r["sharpe"] - 0.02 * max(0, r["dd"] - 15),
        reverse=True,
    )
    for r in balanced[:5]:
        print(
            f"  regime={r['use_regime_filter']} adx={r['adx_threshold']} "
            f"stop={r['stop_atr_mult']} tgt={r['target_atr_mult']} "
            f"lock={r['profit_lock_atr']} tstop={r['time_stop_bars']} "
            f"=> trades={r['trades']} ret={r['return']:.2f}% sharpe={r['sharpe']:.3f} dd={r['dd']:.2f}%"
        )


if __name__ == "__main__":
    main()
