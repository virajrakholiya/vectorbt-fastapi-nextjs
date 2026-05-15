"""
Buy-and-hold benchmark for comparison with the `pro_trader` strategy.

Setup:
  - Symbols: RELIANCE.NS, TCS.NS, INFY.NS (yfinance)
  - Period: 2023-01-01 -> 2026-05-15 (uses latest available if future)
  - Capital: INR 50,000, split equally
  - Costs: 0.10% fee + 0.05% slippage on entry (and on exit at MTM end)
"""

from __future__ import annotations

import sys
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf


SYMBOLS = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
START = "2023-01-01"
END = "2026-05-15"
CAPITAL = 50_000.0
FEE = 0.001          # 0.10%
SLIPPAGE = 0.0005    # 0.05%


def fetch(symbol: str) -> pd.DataFrame:
    df = yf.download(
        symbol,
        start=START,
        end=END,
        progress=False,
        auto_adjust=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


def main() -> int:
    per_symbol_capital = CAPITAL / len(SYMBOLS)
    print(f"Initial capital      : INR {CAPITAL:,.2f}")
    print(f"Per-symbol allocation: INR {per_symbol_capital:,.2f}")
    print(f"Entry cost (fee+slip): {(FEE + SLIPPAGE) * 100:.3f}% each side")
    print()

    closes: dict[str, pd.Series] = {}
    entries: dict[str, dict] = {}

    for sym in SYMBOLS:
        df = fetch(sym)
        if df.empty:
            print(f"  [WARN] no data for {sym}", file=sys.stderr)
            continue
        closes[sym] = df["Close"]

        entry_date = df.index[0]
        entry_close = float(df["Close"].iloc[0])
        # Effective buy price: close * (1 + slippage); fee taken from cash separately
        buy_price = entry_close * (1.0 + SLIPPAGE)
        invested_after_fee = per_symbol_capital * (1.0 - FEE)
        shares = invested_after_fee / buy_price

        entries[sym] = {
            "entry_date": entry_date,
            "entry_close": entry_close,
            "buy_price": buy_price,
            "shares": shares,
            "cost": per_symbol_capital,
        }

    # Build aligned equity curve on union of dates
    all_idx = sorted(set().union(*[c.index for c in closes.values()]))
    eq = pd.DataFrame(index=pd.DatetimeIndex(all_idx))
    for sym, s in closes.items():
        eq[sym] = s.reindex(eq.index).ffill()

    # Per-symbol mark-to-market value (shares * close)
    mtm = pd.DataFrame(index=eq.index)
    for sym in SYMBOLS:
        if sym not in entries:
            continue
        mtm[sym] = eq[sym] * entries[sym]["shares"]
    portfolio = mtm.sum(axis=1)

    actual_end = portfolio.index[-1]
    actual_start = portfolio.index[0]

    # Final exit: close * (1 - slippage), then minus fee on the proceeds
    final_per_sym = {}
    final_total_gross = 0.0
    for sym in SYMBOLS:
        if sym not in entries:
            continue
        last_close = float(eq[sym].iloc[-1])
        sell_price = last_close * (1.0 - SLIPPAGE)
        gross = entries[sym]["shares"] * sell_price
        net = gross * (1.0 - FEE)
        final_per_sym[sym] = {
            "last_close": last_close,
            "sell_price": sell_price,
            "gross": gross,
            "net": net,
            "pnl": net - entries[sym]["cost"],
            "ret_pct": (net - entries[sym]["cost"]) / entries[sym]["cost"] * 100,
        }
        final_total_gross += net

    final_capital = final_total_gross
    total_return_pct = (final_capital - CAPITAL) / CAPITAL * 100

    # CAGR on actual elapsed period
    years = (actual_end - actual_start).days / 365.25
    cagr = ((final_capital / CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else 0.0

    # Daily returns from MTM portfolio (without final-exit fees, standard convention)
    daily_ret = portfolio.pct_change().dropna()
    sharpe = (
        np.sqrt(252) * daily_ret.mean() / daily_ret.std(ddof=0)
        if daily_ret.std(ddof=0) > 0
        else 0.0
    )

    # Max drawdown on MTM portfolio
    running_max = portfolio.cummax()
    drawdown = (portfolio - running_max) / running_max
    max_dd_pct = drawdown.min() * 100

    print("=" * 66)
    print("BUY-AND-HOLD BENCHMARK")
    print("=" * 66)
    print(f"Requested period : {START}  ->  {END}")
    print(f"Actual period    : {actual_start.date()}  ->  {actual_end.date()}")
    if str(actual_end.date()) < END:
        print(f"  [NOTE] yfinance returned data only through {actual_end.date()};")
        print(f"         using latest available close as proxy.")
    print(f"Elapsed years    : {years:.3f}")
    print()
    print(f"Final capital    : INR {final_capital:,.2f}")
    print(f"Net P&L          : INR {final_capital - CAPITAL:,.2f}")
    print(f"Total return     : {total_return_pct:+.2f}%")
    print(f"CAGR             : {cagr:+.2f}%")
    print(f"Sharpe (rf=0)    : {sharpe:.3f}")
    print(f"Max drawdown     : {max_dd_pct:.2f}%")
    print()
    print("Per-symbol contribution")
    print("-" * 66)
    print(f"{'Symbol':<13}{'Entry':>12}{'Last':>12}{'Shares':>10}{'P&L':>12}{'Ret%':>8}")
    for sym in SYMBOLS:
        if sym not in entries:
            continue
        e = entries[sym]
        f = final_per_sym[sym]
        print(
            f"{sym:<13}{e['entry_close']:>12.2f}{f['last_close']:>12.2f}"
            f"{e['shares']:>10.3f}{f['pnl']:>12.2f}{f['ret_pct']:>8.2f}"
        )

    print()
    print("=" * 66)
    print("COMPARISON vs `pro_trader` strategy")
    print("=" * 66)
    print(f"{'Metric':<18}{'Strategy':>15}{'Buy & Hold':>15}{'Delta':>15}")
    strat = {"pnl": 7207.36, "ret": 14.41, "sharpe": 0.482, "mdd": -18.23}
    print(f"{'Net P&L (INR)':<18}{strat['pnl']:>15.2f}{final_capital - CAPITAL:>15.2f}"
          f"{(final_capital - CAPITAL) - strat['pnl']:>15.2f}")
    print(f"{'Total return %':<18}{strat['ret']:>15.2f}{total_return_pct:>15.2f}"
          f"{total_return_pct - strat['ret']:>+15.2f}")
    print(f"{'Sharpe':<18}{strat['sharpe']:>15.3f}{sharpe:>15.3f}"
          f"{sharpe - strat['sharpe']:>+15.3f}")
    print(f"{'Max DD %':<18}{strat['mdd']:>15.2f}{max_dd_pct:>15.2f}"
          f"{max_dd_pct - strat['mdd']:>+15.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
