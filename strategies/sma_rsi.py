from .base import BaseStrategy
import pandas as pd
import numpy as np
import vectorbt as vbt


class SMARSIStrategy(BaseStrategy):
    """
    SMA crossover with RSI confirmation and ATR-based trailing stop.

    Buy:  fast SMA crosses above slow SMA AND RSI < rsi_overbought
    Sell: fast SMA crosses below slow SMA OR RSI > rsi_overbought OR price drops below trailing stop

    Filters out false breakouts using RSI; protects gains using ATR stop loss.
    """

    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        fast_window = int(self.params.get("fast_window", 20))
        slow_window = int(self.params.get("slow_window", 50))
        rsi_window = int(self.params.get("rsi_window", 14))
        rsi_overbought = float(self.params.get("rsi_overbought", 70))
        rsi_oversold = float(self.params.get("rsi_oversold", 30))
        stop_loss_pct = float(self.params.get("stop_loss_pct", 0.05))

        if isinstance(self.data.columns, pd.MultiIndex):
            close_prices = self.data.xs("close", axis=1, level=1)
        else:
            close_prices = self.data["close"]

        # Indicators
        fast_sma = vbt.MA.run(close_prices, fast_window).ma
        slow_sma = vbt.MA.run(close_prices, slow_window).ma
        rsi = vbt.RSI.run(close_prices, rsi_window).rsi

        # Crossover signals (drop multi-level params from columns)
        sma_cross_up = (fast_sma > slow_sma) & (fast_sma.shift(1) <= slow_sma.shift(1))
        sma_cross_down = (fast_sma < slow_sma) & (fast_sma.shift(1) >= slow_sma.shift(1))

        # Buy: SMA crossover up AND RSI not overbought AND RSI rising from oversold
        entries = sma_cross_up & (rsi < rsi_overbought) & (rsi > rsi_oversold)

        # Sell: SMA crossover down OR RSI overbought
        exits = sma_cross_down | (rsi > rsi_overbought)

        # Trailing stop loss: track running max since entry, exit if price drops > stop_loss_pct
        if isinstance(close_prices, pd.DataFrame):
            for col in close_prices.columns:
                stop_exits = self._stop_loss_signals(
                    close_prices[col], entries[col], exits[col], stop_loss_pct
                )
                exits[col] = exits[col] | stop_exits
        else:
            stop_exits = self._stop_loss_signals(close_prices, entries, exits, stop_loss_pct)
            exits = exits | stop_exits

        entries = entries.fillna(False).astype(bool)
        exits = exits.fillna(False).astype(bool)

        return entries, exits

    @staticmethod
    def _stop_loss_signals(
        prices: pd.Series, entries: pd.Series, exits: pd.Series, stop_pct: float
    ) -> pd.Series:
        """Generate stop-loss exit signals based on running peak since entry."""
        stop_exits = pd.Series(False, index=prices.index)
        in_position = False
        peak_price = 0.0

        for i in range(len(prices)):
            if not in_position and bool(entries.iloc[i]):
                in_position = True
                peak_price = prices.iloc[i]
            elif in_position:
                price = prices.iloc[i]
                if price > peak_price:
                    peak_price = price
                if price < peak_price * (1 - stop_pct):
                    stop_exits.iloc[i] = True
                    in_position = False
                elif bool(exits.iloc[i]):
                    in_position = False

        return stop_exits
