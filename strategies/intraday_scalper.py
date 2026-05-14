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
        max_pyramid: int = 2,     # FIX: cap pyramid depth to avoid buy clusters
    ) -> pd.Series:
        """
        Generate exits based on profit target, trailing stop, or max hold time.

        Fixes applied vs original:
          - Exit fires on next bar (pending_exit), not same bar (removes look-ahead).
          - Re-entry blocked on the bar exit fires AND the bar condition is triggered.
          - Pyramid depth capped at max_pyramid (was unlimited, causing buy clusters).
          - 2-bar cooldown after exit before accepting new entries.
        """
        exits        = pd.Series(False, index=prices.index)
        in_pos       = False
        avg_entry    = 0.0
        units        = 0
        bars_held    = 0
        peak         = 0.0
        pending_exit = False   # exit fires on next bar
        cooldown     = 0       # bars before new entries allowed after exit

        for i in range(len(prices)):
            price = prices.iloc[i]

            # ---- FIX 1: apply pending exit, skip entry on this bar ----
            if pending_exit:
                if i > 0:
                    exits.iloc[i] = True
                pending_exit = False
                in_pos    = False
                units     = 0
                avg_entry = 0.0
                peak      = 0.0
                bars_held = 0
                cooldown  = 2   # no re-entry for 2 bars
                continue        # skip entry check on exit bar

            # ---- decrement cooldown ----
            if cooldown > 0:
                cooldown -= 1

            # ---- check exit conditions BEFORE processing new entry ----
            if in_pos:
                bars_held += 1
                if price > peak:
                    peak = price

                hit_target = (price - avg_entry) / avg_entry >= profit_target
                hit_stop   = (price - peak) / peak <= -stop_loss
                timed_out  = bars_held >= max_hold

                if hit_target or hit_stop or timed_out:
                    pending_exit = True   # FIX 2: exit next bar
                    continue              # FIX 3: skip new entry on trigger bar

            # ---- new entry — only if not in cooldown, not pending exit ----
            if (
                bool(entries.iloc[i])
                and not pending_exit     # FIX 4: never enter while exit is waiting
                and cooldown == 0
            ):
                if not in_pos:
                    in_pos    = True
                    avg_entry = price
                    units     = 1
                    peak      = price
                    bars_held = 0
                elif units < max_pyramid:     # FIX 5: cap pyramid depth
                    avg_entry = (avg_entry * units + price) / (units + 1)
                    units    += 1

        return exits
