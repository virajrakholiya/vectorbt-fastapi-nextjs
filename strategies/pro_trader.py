from .base import BaseStrategy, align_columns
import pandas as pd
import numpy as np
import vectorbt as vbt


class ProTraderStrategy(BaseStrategy):
    """
    Multi-signal trend follower with volatility-aware stops.

    Built for stable, profitable, high-frequency trading on liquid stocks.

    Bias filter (must be true to enter):
      - EMA stack bullish: EMA9 > EMA21 > EMA50
      - ADX > adx_threshold (trending market, avoids chop)

    Entry triggers (any one fires when bias holds):
      T1. MACD bullish cross (MACD line crosses above signal)
      T2. RSI oversold reversal (RSI dipped below rsi_oversold then crosses back above)
      T3. Donchian breakout (close > N-day prior high)
      T4. Bollinger lower-band bounce (close touched lower BB then closes back above mid)

    Exits (volatility-adaptive):
      - ATR trailing stop: highest close since entry minus stop_atr_mult * ATR
      - ATR profit target: entry + target_atr_mult * ATR
      - Trend break: EMA9 crosses below EMA21

    Position size 0.4 so up to 2-3 stacked entries fit per symbol.
    """

    accumulate = True
    entry_size = 0.4

    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        ema_fast = int(self.params.get("ema_fast", 9))
        ema_mid = int(self.params.get("ema_mid", 21))
        ema_slow = int(self.params.get("ema_slow", 50))
        rsi_window = int(self.params.get("rsi_window", 14))
        rsi_oversold = float(self.params.get("rsi_oversold", 35))
        adx_window = int(self.params.get("adx_window", 14))
        adx_threshold = float(self.params.get("adx_threshold", 18))
        donchian_window = int(self.params.get("donchian_window", 20))
        bb_window = int(self.params.get("bb_window", 20))
        bb_std = float(self.params.get("bb_std", 2.0))
        atr_window = int(self.params.get("atr_window", 14))
        stop_atr_mult = float(self.params.get("stop_atr_mult", 1.8))
        target_atr_mult = float(self.params.get("target_atr_mult", 4.0))
        macd_fast = int(self.params.get("macd_fast", 12))
        macd_slow = int(self.params.get("macd_slow", 26))
        macd_signal = int(self.params.get("macd_signal", 9))

        if isinstance(self.data.columns, pd.MultiIndex):
            close = self.data.xs("close", axis=1, level=1)
            high = self.data.xs("high", axis=1, level=1)
            low = self.data.xs("low", axis=1, level=1)
        else:
            close = self.data["close"]
            high = self.data["high"]
            low = self.data["low"]

        # EMAs
        ema_f = align_columns(vbt.MA.run(close, ema_fast, ewm=True).ma, close)
        ema_m = align_columns(vbt.MA.run(close, ema_mid, ewm=True).ma, close)
        ema_s = align_columns(vbt.MA.run(close, ema_slow, ewm=True).ma, close)

        # RSI
        rsi = align_columns(vbt.RSI.run(close, rsi_window).rsi, close)

        # ATR (volatility) — manual computation since vbt.ATR API differs across versions
        atr = self._compute_atr(high, low, close, atr_window)

        # ADX (trend strength) — manual computation
        adx = self._compute_adx(high, low, close, adx_window)

        # MACD
        macd_obj = vbt.MACD.run(close, fast_window=macd_fast, slow_window=macd_slow, signal_window=macd_signal)
        macd_line = align_columns(macd_obj.macd, close)
        macd_sig = align_columns(macd_obj.signal, close)

        # Donchian high (prior N-day max)
        donchian_high = high.shift(1).rolling(donchian_window).max() if isinstance(high, pd.DataFrame) else high.shift(1).rolling(donchian_window).max()

        # Bollinger Bands
        bb_obj = vbt.BBANDS.run(close, window=bb_window, alpha=bb_std)
        bb_lower = align_columns(bb_obj.lower, close)
        bb_middle = align_columns(bb_obj.middle, close)

        # Bias: EMA stack bullish + ADX trending
        bias = (ema_f > ema_m) & (ema_m > ema_s) & (adx > adx_threshold)

        # T1: MACD bullish cross
        macd_cross = (macd_line > macd_sig) & (macd_line.shift(1) <= macd_sig.shift(1))

        # T2: RSI oversold reversal — was below oversold in last 3 bars, now above oversold
        rsi_dipped = (rsi.shift(1) < rsi_oversold) | (rsi.shift(2) < rsi_oversold) | (rsi.shift(3) < rsi_oversold)
        rsi_recovered = rsi > rsi_oversold
        rsi_reversal = rsi_dipped & rsi_recovered & (rsi.shift(1) <= rsi)

        # T3: Donchian breakout
        breakout = close > donchian_high

        # T4: BB lower band bounce
        touched_lower = (close.shift(1) <= bb_lower.shift(1)) | (low.shift(1) <= bb_lower.shift(1))
        bounce = touched_lower & (close > bb_middle.shift(1))

        entries = bias & (macd_cross | rsi_reversal | breakout | bounce)

        # Trend-break exit signal
        ema_break = (ema_f < ema_m) & (ema_f.shift(1) >= ema_m.shift(1))

        # Apply ATR-based stops per symbol
        if isinstance(close, pd.DataFrame):
            exits = pd.DataFrame(False, index=close.index, columns=close.columns)
            for col in close.columns:
                exits[col] = self._exit_signals(
                    close[col], atr[col], entries[col], ema_break[col],
                    stop_atr_mult, target_atr_mult,
                )
        else:
            exits = self._exit_signals(
                close, atr, entries, ema_break, stop_atr_mult, target_atr_mult
            )

        entries = entries.fillna(False).astype(bool)
        exits = exits.fillna(False).astype(bool)

        return entries, exits

    @staticmethod
    def _compute_atr(high, low, close, window):
        """Average True Range — works on Series or DataFrame."""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        if isinstance(tr1, pd.DataFrame):
            tr = pd.concat([tr1, tr2, tr3]).groupby(level=0).max()
        else:
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1 / window, adjust=False).mean()
        return atr

    @staticmethod
    def _compute_adx(high, low, close, window):
        """Average Directional Index — works on Series or DataFrame."""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        if isinstance(tr1, pd.DataFrame):
            tr = pd.concat([tr1, tr2, tr3]).groupby(level=0).max()
        else:
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        atr_v = tr.ewm(alpha=1 / window, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr_v.replace(0, np.nan)
        minus_di = 100 * minus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr_v.replace(0, np.nan)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / window, adjust=False).mean()
        return adx.fillna(0)

    @staticmethod
    def _exit_signals(
        prices: pd.Series, atrs: pd.Series, entries: pd.Series, trend_break: pd.Series,
        stop_mult: float, target_mult: float,
    ) -> pd.Series:
        """ATR-based trailing stop + ATR profit target + trend break exits."""
        exits = pd.Series(False, index=prices.index)
        in_pos = False
        entry_price = 0.0
        peak = 0.0
        entry_atr = 0.0

        for i in range(len(prices)):
            price = prices.iloc[i]
            atr_v = atrs.iloc[i] if not pd.isna(atrs.iloc[i]) else 0.0

            if not in_pos:
                if bool(entries.iloc[i]) and atr_v > 0:
                    in_pos = True
                    entry_price = price
                    peak = price
                    entry_atr = atr_v
                continue

            if price > peak:
                peak = price

            trailing_stop = peak - stop_mult * entry_atr
            target_price = entry_price + target_mult * entry_atr

            hit_target = price >= target_price
            hit_stop = price <= trailing_stop
            broke_trend = bool(trend_break.iloc[i])

            if hit_target or hit_stop or broke_trend:
                exits.iloc[i] = True
                in_pos = False
                entry_price = 0.0
                peak = 0.0
                entry_atr = 0.0

        return exits
