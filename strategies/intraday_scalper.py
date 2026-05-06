from .base import BaseStrategy, align_columns
import pandas as pd
import numpy as np
import vectorbt as vbt


class IntradayScalperStrategy(BaseStrategy):
    """
    Stock-equivalent of intraday options scalper (ORB + EMA + Pyramiding + EOD-style exit).

    Mirrors the screenshot trade pattern:
    - Bias detection via fast/slow EMA cross + RSI 50 line (direction flip)
    - Opening Range Breakout: enters when close breaks the rolling N-bar high (long-side)
    - Pyramiding: adds to winning position on continued breakout (Fib-ish scale-in)
    - Quick scalp: tight profit target (% based) and trailing stop
    - EOD-equivalent: forced flat after max_hold bars

    On daily data this approximates a multi-day swing version of the strategy;
    drop in 5-min data and the same code becomes a true intraday scalper.
    """

    accumulate = True  # enable pyramiding
    entry_size = 0.25  # each entry uses 25% of available cash → up to 4 stacked entries

    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        breakout_window = int(self.params.get("breakout_window", 5))
        ema_fast = int(self.params.get("ema_fast", 9))
        ema_slow = int(self.params.get("ema_slow", 21))
        rsi_window = int(self.params.get("rsi_window", 14))
        rsi_floor = float(self.params.get("rsi_floor", 45))
        rsi_ceiling = float(self.params.get("rsi_ceiling", 75))
        max_hold = int(self.params.get("max_hold", 5))
        profit_target = float(self.params.get("profit_target", 0.03))
        stop_loss = float(self.params.get("stop_loss", 0.015))

        if isinstance(self.data.columns, pd.MultiIndex):
            close = self.data.xs("close", axis=1, level=1)
            high = self.data.xs("high", axis=1, level=1)
        else:
            close = self.data["close"]
            high = self.data["high"]

        ema_f = align_columns(vbt.MA.run(close, ema_fast, ewm=True).ma, close)
        ema_s = align_columns(vbt.MA.run(close, ema_slow, ewm=True).ma, close)
        rsi = align_columns(vbt.RSI.run(close, rsi_window).rsi, close)

        # Rolling N-bar high → ORB-equivalent breakout level (use prior bar so today can break it)
        prior_high = high.shift(1).rolling(breakout_window).max()
        breakout = close > prior_high

        bullish_bias = (ema_f > ema_s) & (rsi > rsi_floor) & (rsi < rsi_ceiling)

        # Pyramid entry signal: every bar where breakout + bias holds (engine accumulates)
        entries = (breakout & bullish_bias).fillna(False).astype(bool)

        if isinstance(close, pd.DataFrame):
            exits = pd.DataFrame(False, index=close.index, columns=close.columns)
            for col in close.columns:
                exits[col] = self._exit_signals(
                    close[col], entries[col], max_hold, profit_target, stop_loss
                )
        else:
            exits = self._exit_signals(close, entries, max_hold, profit_target, stop_loss)

        exits = exits.fillna(False).astype(bool)
        return entries, exits

    @staticmethod
    def _exit_signals(
        prices: pd.Series,
        entries: pd.Series,
        max_hold: int,
        profit_target: float,
        stop_loss: float,
    ) -> pd.Series:
        """Generate exits based on profit target, trailing stop, or max hold time."""
        exits = pd.Series(False, index=prices.index)

        in_pos = False
        avg_entry = 0.0
        units = 0
        bars_held = 0
        peak = 0.0

        for i in range(len(prices)):
            price = prices.iloc[i]

            if entries.iloc[i]:
                if not in_pos:
                    in_pos = True
                    avg_entry = price
                    units = 1
                    peak = price
                    bars_held = 0
                else:
                    avg_entry = (avg_entry * units + price) / (units + 1)
                    units += 1

            if not in_pos:
                continue

            bars_held += 1
            if price > peak:
                peak = price

            hit_target = (price - avg_entry) / avg_entry >= profit_target
            hit_stop = (price - peak) / peak <= -stop_loss
            timed_out = bars_held >= max_hold

            if hit_target or hit_stop or timed_out:
                exits.iloc[i] = True
                in_pos = False
                units = 0
                avg_entry = 0.0
                peak = 0.0
                bars_held = 0

        return exits
