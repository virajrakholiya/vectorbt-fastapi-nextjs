import re
import vectorbt as vbt
import pandas as pd

# Match symbol portion in vectorBT Column field, e.g. "(10, 50, INFY)" -> "INFY"
_SYMBOL_RE = re.compile(r"([A-Z0-9._-]{2,})")

# --- Realistic NSE equity transaction costs (discount-broker / Zerodha-style) ---
# Applied as a blended per-order percentage (`fees`) + flat per-order charge (`fixed_fees`).
# STT and stamp duty are single-side in reality (sell-only / buy-only); we average them
# across the entry+exit legs into one per-order rate so vectorbt's symmetric fee model
# still reflects the true round-trip cost.
#
# Intraday (MIS) per order:
#   STT 0.025% (sell) -> 0.0125% avg | exch txn 0.00297% | stamp 0.003% (buy) -> 0.0015% avg
#   SEBI 0.0001% | GST 18% on txn -> 0.000535%   => sum ~0.0176%
#   brokerage flat Rs20 + 18% GST = Rs23.6 per order
_INTRADAY_FEES_PCT = 0.000176
_INTRADAY_FIXED_FEES = 23.6
#
# Delivery (CNC) per order:
#   STT 0.1% (both sides) | exch txn 0.00297% | stamp 0.015% (buy) -> 0.0075% avg
#   SEBI 0.0001% | GST 18% on txn -> 0.000535%   => sum ~0.111%
#   brokerage 0 (free delivery)
_DELIVERY_FEES_PCT = 0.00111
_DELIVERY_FIXED_FEES = 0.0

# NSE equity session = 375 trading minutes/day, ~252 trading days/year.
_NSE_TRADING_MINUTES_PER_YEAR = 252 * 375  # 94,500


def _resolve_freq(timeframe: str):
    """
    Map a UI timeframe to (bar_freq, year_freq) so vectorbt annualizes correctly.

    vectorbt's annualization factor = year_freq / bar_freq. Hardcoding "D" made it
    treat every intraday bar as one calendar day, inflating/garbling Sharpe by 25-100x.
    For intraday we anchor year_freq to NSE *trading* minutes (not 365 calendar days),
    and for daily we use 252 trading days (equity convention) instead of 365.
    """
    tf = str(timeframe).upper()
    if tf in ("D", "1D"):
        return "1D", pd.Timedelta(days=252)
    if tf in ("W", "1W"):
        return "1W", pd.Timedelta(weeks=52)
    if tf in ("M", "1M"):
        return "30D", pd.Timedelta(days=360)
    # intraday: timeframe is a minute count as a string ("1", "5", "15", "60", "240"...)
    try:
        n = int(tf)
    except (TypeError, ValueError):
        return "1D", pd.Timedelta(days=252)
    return f"{n}min", pd.Timedelta(minutes=_NSE_TRADING_MINUTES_PER_YEAR)


def _extract_symbol(column_value, fallback_symbols=None):
    """Pull the trading symbol out of a vectorBT Column field."""
    if column_value is None:
        return "Unknown"

    if isinstance(column_value, tuple):
        for item in reversed(column_value):
            if isinstance(item, str):
                return item
        return str(column_value[-1])

    s = str(column_value)
    if fallback_symbols:
        for sym in fallback_symbols:
            if sym in s:
                return sym

    matches = _SYMBOL_RE.findall(s)
    if matches:
        return matches[-1]
    return s


class BacktestEngine:
    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 50000.0,
        fees: float = 0.001,
        slippage: float = 0.0005,
        intraday_mode: bool = False,
        leverage: float = 1.0,
        timeframe: str = "1D",
    ):
        self.data = data
        self.initial_capital = initial_capital
        self.fees = fees
        self.slippage = slippage
        self.intraday_mode = intraday_mode
        self.leverage = leverage
        self.timeframe = timeframe

    def run(
        self,
        entries: pd.DataFrame,
        exits: pd.DataFrame,
        size: float = 1.0,
        accumulate: bool = False,
        direction: str = "long",
    ) -> vbt.Portfolio:
        """
        Run VectorBT portfolio simulation.
        Multi-symbol portfolios are grouped with shared cash to behave as a unified portfolio.
        """
        if isinstance(self.data.columns, pd.MultiIndex):
            close_prices = self.data.xs("close", axis=1, level=1)
        else:
            close_prices = self.data["close"]

        is_multi_symbol = isinstance(close_prices, pd.DataFrame) and close_prices.shape[1] > 1

        vbt_entries = entries if direction == "long" else None
        vbt_exits = exits if direction == "long" else None
        vbt_short_entries = entries if direction == "short" else None
        vbt_short_exits = exits if direction == "short" else None

        # Realistic NSE cost model: intraday (MIS) leverages size and pays flat
        # brokerage + taxes; delivery (CNC) is unleveraged with higher STT.
        if self.intraday_mode:
            effective_size = size * self.leverage
            fees_pct = _INTRADAY_FEES_PCT
            fixed_fees = _INTRADAY_FIXED_FEES
        else:
            effective_size = size
            fees_pct = _DELIVERY_FEES_PCT
            fixed_fees = _DELIVERY_FIXED_FEES

        # Correct annualization: bar spacing + trading-time year (see _resolve_freq).
        # `year_freq` isn't a from_signals kwarg in this vectorbt build, so set it on
        # the global returns config. Safe here: run() + get_metrics() execute in one
        # synchronous stretch per request (no event-loop yield between them).
        freq, year_freq = _resolve_freq(self.timeframe)
        vbt.settings.returns["year_freq"] = year_freq

        portfolio = vbt.Portfolio.from_signals(
            close=close_prices,
            entries=vbt_entries,
            exits=vbt_exits,
            short_entries=vbt_short_entries,
            short_exits=vbt_short_exits,
            init_cash=self.initial_capital,
            fees=fees_pct,
            fixed_fees=fixed_fees,
            slippage=self.slippage,
            size=effective_size,
            size_type="percent",
            freq=freq,
            group_by=True if is_multi_symbol else None,
            cash_sharing=True if is_multi_symbol else False,
            accumulate=accumulate,
        )

        return portfolio

    def get_metrics(self, portfolio: vbt.Portfolio) -> dict:
        stats = portfolio.stats()

        total_fees = 0.0
        trades_records = portfolio.trades.records_readable
        if not trades_records.empty:
            entry_fees = trades_records["Entry Fees"].sum() if "Entry Fees" in trades_records.columns else 0.0
            exit_fees = trades_records["Exit Fees"].sum() if "Exit Fees" in trades_records.columns else 0.0
            total_fees = float(entry_fees) + float(exit_fees)

        portfolio_values = portfolio.value()
        if isinstance(portfolio_values, pd.DataFrame):
            final_value = float(portfolio_values.iloc[-1].sum())
        else:
            final_value = float(portfolio_values.iloc[-1])

        return {
            "total_return": float(stats.get("Total Return [%]", 0.0)),
            "win_rate": float(stats.get("Win Rate [%]", 0.0)),
            "max_drawdown": float(stats.get("Max Drawdown [%]", 0.0)),
            "sharpe_ratio": float(stats.get("Sharpe Ratio", 0.0)),
            "total_trades": int(stats.get("Total Trades", 0)),
            "net_profit": float(stats.get("Total Return [%]", 0.0)) / 100 * self.initial_capital,
            "fees_paid": total_fees,
            "final_value": final_value,
            "initial_capital": float(self.initial_capital),
        }

    def get_charts(self, portfolio: vbt.Portfolio, symbols: list = None) -> dict:
        """Aggregate equity & drawdown across symbols + per-symbol equity curves."""
        # Combined (grouped) view — single series for total portfolio
        try:
            total_values = portfolio.value()
        except Exception:
            total_values = pd.Series(dtype=float)

        # Force per-asset view for symbol breakdown (even when group_by=True)
        try:
            per_asset_values = portfolio.value(group_by=False)
        except Exception:
            per_asset_values = total_values

        per_symbol_equity = {}
        if isinstance(per_asset_values, pd.DataFrame):
            for col in per_asset_values.columns:
                sym = _extract_symbol(col, symbols)
                series = per_asset_values[col]
                per_symbol_equity[sym] = [
                    {"date": idx.strftime("%Y-%m-%d %H:%M"), "value": float(v)}
                    for idx, v in series.items()
                ]

        if isinstance(total_values, pd.DataFrame):
            total_values = total_values.sum(axis=1)

        # True portfolio drawdown from the aggregated equity curve.
        # (Previously averaged per-symbol drawdowns — mathematically meaningless.)
        if len(total_values) > 0:
            running_peak = total_values.cummax()
            total_drawdown = total_values / running_peak - 1.0
        else:
            total_drawdown = pd.Series(dtype=float)

        equity_curve = [
            {"date": idx.strftime("%Y-%m-%d %H:%M"), "value": float(val)}
            for idx, val in total_values.items()
        ]
        drawdown_series = [
            {"date": idx.strftime("%Y-%m-%d %H:%M"), "value": float(val) * 100}
            for idx, val in total_drawdown.items()
        ]

        return {
            "equity_curve": equity_curve,
            "drawdown": drawdown_series,
            "per_symbol_equity": per_symbol_equity,
        }

    def get_trades(self, portfolio: vbt.Portfolio, symbols: list = None) -> list:
        trades_df = portfolio.trades.records_readable
        if trades_df.empty:
            return []

        cols = trades_df.columns
        trades_list = []

        for _, row in trades_df.iterrows():
            entry_fees = float(row["Entry Fees"]) if "Entry Fees" in cols and pd.notnull(row.get("Entry Fees")) else 0.0
            exit_fees = float(row["Exit Fees"]) if "Exit Fees" in cols and pd.notnull(row.get("Exit Fees")) else 0.0

            symbol = _extract_symbol(row.get("Column"), symbols)

            entry_price_val = float(row["Avg Entry Price"]) if pd.notnull(row.get("Avg Entry Price")) else None
            exit_price_val = float(row["Avg Exit Price"]) if pd.notnull(row.get("Avg Exit Price")) else None
            qty = float(row["Size"]) if pd.notnull(row.get("Size")) else 0.0

            trade_amount = entry_price_val * qty if entry_price_val is not None else 0.0
            exit_amount = exit_price_val * qty if exit_price_val is not None else None

            trades_list.append({
                "symbol": symbol,
                "entry_date": int(row["Entry Timestamp"].timestamp()) if pd.notnull(row.get("Entry Timestamp")) else None,
                "exit_date": int(row["Exit Timestamp"].timestamp()) if pd.notnull(row.get("Exit Timestamp")) else None,
                "entry_price": entry_price_val,
                "exit_price": exit_price_val,
                "quantity": qty,
                "trade_amount": trade_amount,
                "exit_amount": exit_amount,
                "profit_loss": float(row["PnL"]) if pd.notnull(row.get("PnL")) else 0.0,
                "return_pct": float(row["Return"]) * 100 if pd.notnull(row.get("Return")) else 0.0,
                "fees": entry_fees + exit_fees,
                "status": str(row.get("Status", "")),
                "direction": str(row.get("Direction", "Long")),
            })

        # Sort newest first by entry_date
        trades_list.sort(key=lambda t: t["entry_date"] or "", reverse=True)
        return trades_list

    def get_symbol_breakdown(self, trades: list) -> list:
        """Aggregate per-symbol stats from the trades list."""
        if not trades:
            return []

        by_sym = {}
        for t in trades:
            sym = t["symbol"]
            if sym not in by_sym:
                by_sym[sym] = {
                    "symbol": sym,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "open_trades": 0,
                    "total_pnl": 0.0,
                    "best_trade": float("-inf"),
                    "worst_trade": float("inf"),
                    "fees_paid": 0.0,
                    "total_return_pct": 0.0,
                }
            b = by_sym[sym]
            b["total_trades"] += 1
            b["total_pnl"] += t["profit_loss"]
            b["fees_paid"] += t["fees"]
            b["total_return_pct"] += t["return_pct"]

            if t["status"].lower() == "open":
                b["open_trades"] += 1
            elif t["profit_loss"] > 0:
                b["winning_trades"] += 1
            else:
                b["losing_trades"] += 1

            if t["profit_loss"] > b["best_trade"]:
                b["best_trade"] = t["profit_loss"]
            if t["profit_loss"] < b["worst_trade"]:
                b["worst_trade"] = t["profit_loss"]

        breakdown = []
        for sym, b in by_sym.items():
            closed = b["winning_trades"] + b["losing_trades"]
            win_rate = (b["winning_trades"] / closed * 100) if closed > 0 else 0.0
            avg_pnl = (b["total_pnl"] / b["total_trades"]) if b["total_trades"] > 0 else 0.0
            avg_return = (b["total_return_pct"] / b["total_trades"]) if b["total_trades"] > 0 else 0.0

            breakdown.append({
                "symbol": sym,
                "total_trades": b["total_trades"],
                "winning_trades": b["winning_trades"],
                "losing_trades": b["losing_trades"],
                "open_trades": b["open_trades"],
                "win_rate": win_rate,
                "total_pnl": b["total_pnl"],
                "avg_pnl_per_trade": avg_pnl,
                "avg_return_pct": avg_return,
                "best_trade": b["best_trade"] if b["best_trade"] != float("-inf") else 0.0,
                "worst_trade": b["worst_trade"] if b["worst_trade"] != float("inf") else 0.0,
                "fees_paid": b["fees_paid"],
            })

        breakdown.sort(key=lambda x: x["total_pnl"], reverse=True)
        return breakdown
