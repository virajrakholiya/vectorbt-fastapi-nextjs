import re
import vectorbt as vbt
import pandas as pd

# Match symbol portion in vectorBT Column field, e.g. "(10, 50, INFY)" -> "INFY"
_SYMBOL_RE = re.compile(r"([A-Z0-9._-]{2,})")


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
    ):
        self.data = data
        self.initial_capital = initial_capital
        self.fees = fees
        self.slippage = slippage

    def run(self, entries: pd.DataFrame, exits: pd.DataFrame, size: float = 1.0) -> vbt.Portfolio:
        """
        Run VectorBT portfolio simulation.
        Multi-symbol portfolios are grouped with shared cash to behave as a unified portfolio.
        """
        if isinstance(self.data.columns, pd.MultiIndex):
            close_prices = self.data.xs("close", axis=1, level=1)
        else:
            close_prices = self.data["close"]

        is_multi_symbol = isinstance(close_prices, pd.DataFrame) and close_prices.shape[1] > 1

        portfolio = vbt.Portfolio.from_signals(
            close=close_prices,
            entries=entries,
            exits=exits,
            init_cash=self.initial_capital,
            fees=self.fees,
            slippage=self.slippage,
            size=size,
            size_type="percent",
            freq="D",
            group_by=True if is_multi_symbol else None,
            cash_sharing=True if is_multi_symbol else False,
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
        values = portfolio.value()
        drawdowns = portfolio.drawdown()

        per_symbol_equity = {}

        if isinstance(values, pd.DataFrame):
            for col in values.columns:
                sym = _extract_symbol(col, symbols)
                series = values[col]
                per_symbol_equity[sym] = [
                    {"date": idx.strftime("%Y-%m-%d"), "value": float(v)}
                    for idx, v in series.items()
                ]
            total_values = values.sum(axis=1)
        else:
            total_values = values

        if isinstance(drawdowns, pd.DataFrame):
            total_drawdown = drawdowns.mean(axis=1)
        else:
            total_drawdown = drawdowns

        equity_curve = [
            {"date": idx.strftime("%Y-%m-%d"), "value": float(val)}
            for idx, val in total_values.items()
        ]
        drawdown_series = [
            {"date": idx.strftime("%Y-%m-%d"), "value": float(val) * 100}
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

            trades_list.append({
                "symbol": symbol,
                "entry_date": row["Entry Timestamp"].strftime("%Y-%m-%d") if pd.notnull(row.get("Entry Timestamp")) else None,
                "exit_date": row["Exit Timestamp"].strftime("%Y-%m-%d") if pd.notnull(row.get("Exit Timestamp")) else None,
                "entry_price": float(row["Avg Entry Price"]) if pd.notnull(row.get("Avg Entry Price")) else None,
                "exit_price": float(row["Avg Exit Price"]) if pd.notnull(row.get("Avg Exit Price")) else None,
                "quantity": float(row["Size"]) if pd.notnull(row.get("Size")) else 0.0,
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
