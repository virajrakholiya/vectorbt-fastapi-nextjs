from .base import BaseStrategy, align_columns
import pandas as pd
import numpy as np
import vectorbt as vbt


class ProTraderStrategy(BaseStrategy):
    """
    Intraday-optimized multi-signal trend follower (15m / 1h).

    Key changes from daily version:
      - Faster indicators scaled for intraday: MACD(5/13/4), RSI(9), ADX(10)
      - ADX threshold raised to 20 + slope guard (ADX must be rising)
      - min_triggers: require N simultaneous signals (default 2) — quality gate
      - Volume confirmation: entry bar volume > vol_mult * 20-bar avg vol
      - NSE session filter: skip first 30 min and last 45 min of session
      - Tighter stop (1.2 ATR), realistic target (2.4 ATR) → 2:1 RR
      - max_entries=1 by default (no pyramiding on intraday)
      - Cooldown 3 bars after any exit

    Bias filter (ALL must be true to enter):
      - EMA stack bullish: ema_fast > ema_mid > ema_slow
      - ADX > adx_threshold (trending market)
      - ADX rising (current ADX > previous ADX) — avoids late-trend entries

    Entry triggers (min_triggers must fire simultaneously):
      T1. MACD bullish cross (fast crosses above signal)
      T2. RSI oversold reversal (dipped below rsi_oversold within 3 bars, recovered)
      T3. Donchian breakout (close > N-bar prior high)
      T4. Bollinger lower-band bounce (touched lower BB then closes above mid)

    Exits:
      - ATR trailing stop: peak_close - stop_atr_mult * ATR
      - ATR profit target: entry + target_atr_mult * ATR
      - Trend break: EMA fast crosses below EMA mid
      - Volume spike reverse: volume > 2x avg AND close < open (bearish surge)
    """

    metadata = {
        "label": "Pro Trader Intraday (ADX + ATR + Multi-Signal)",
        "description": (
            "Intraday trend follower tuned for 15m/1h NSE bars. "
            "Faster MACD/RSI/ADX, requires 2+ simultaneous triggers, "
            "volume confirmation, session-hour filter, 2:1 ATR RR."
        ),
        "params": [
            {"name": "ema_fast",               "label": "EMA Fast",            "type": "number", "default": 8,    "min": 2,   "max": 50},
            {"name": "ema_mid",                "label": "EMA Mid",             "type": "number", "default": 20,   "min": 5,   "max": 100},
            {"name": "ema_slow",               "label": "EMA Slow",            "type": "number", "default": 34,   "min": 10,  "max": 200},
            {"name": "rsi_window",             "label": "RSI Period",          "type": "number", "default": 9,    "min": 2,   "max": 50},
            {"name": "rsi_oversold",           "label": "RSI Oversold",        "type": "number", "default": 35,   "min": 10,  "max": 50},
            {"name": "adx_window",             "label": "ADX Window",          "type": "number", "default": 10,   "min": 5,   "max": 50},
            {"name": "adx_threshold",          "label": "ADX Threshold",       "type": "number", "default": 20,   "min": 5,   "max": 40},
            {"name": "adx_rising",             "label": "ADX Must Rise",       "type": "boolean","default": True},
            {"name": "donchian_window",        "label": "Donchian Window",     "type": "number", "default": 10,   "min": 5,   "max": 100},
            {"name": "bb_window",              "label": "Bollinger Window",    "type": "number", "default": 14,   "min": 5,   "max": 100},
            {"name": "bb_std",                 "label": "Bollinger Std Dev",   "type": "number", "default": 2.0,  "min": 1.0, "max": 3.0,  "step": 0.1},
            {"name": "atr_window",             "label": "ATR Window",          "type": "number", "default": 10,   "min": 5,   "max": 50},
            {"name": "stop_atr_mult",          "label": "Stop ATR Mult",       "type": "number", "default": 1.2,  "min": 0.5, "max": 5.0,  "step": 0.1},
            {"name": "target_atr_mult",        "label": "Target ATR Mult",     "type": "number", "default": 2.4,  "min": 1.0, "max": 10.0, "step": 0.1},
            {"name": "macd_fast",              "label": "MACD Fast",           "type": "number", "default": 5,    "min": 3,   "max": 50},
            {"name": "macd_slow",              "label": "MACD Slow",           "type": "number", "default": 13,   "min": 5,   "max": 100},
            {"name": "macd_signal",            "label": "MACD Signal",         "type": "number", "default": 4,    "min": 2,   "max": 30},
            {"name": "max_entries_per_symbol", "label": "Max Entries / Symbol","type": "number", "default": 1,    "min": 1,   "max": 5},
            {"name": "min_triggers",           "label": "Min Simultaneous Triggers", "type": "number", "default": 2, "min": 1, "max": 4},
            {"name": "vol_mult",               "label": "Volume Filter Mult (0=off)", "type": "number", "default": 1.5, "min": 0.0, "max": 5.0, "step": 0.1},
            {"name": "session_filter",         "label": "NSE Session Filter",  "type": "boolean","default": True},
        ],
    }

    accumulate = True
    entry_size = 0.4

    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        ema_fast        = int(self.params.get("ema_fast", 8))
        ema_mid         = int(self.params.get("ema_mid", 20))
        ema_slow        = int(self.params.get("ema_slow", 34))
        rsi_window      = int(self.params.get("rsi_window", 9))
        rsi_oversold    = float(self.params.get("rsi_oversold", 35))
        adx_window      = int(self.params.get("adx_window", 10))
        adx_threshold   = float(self.params.get("adx_threshold", 20))
        adx_must_rise   = bool(self.params.get("adx_rising", True))
        donchian_window = int(self.params.get("donchian_window", 10))
        bb_window       = int(self.params.get("bb_window", 14))
        bb_std          = float(self.params.get("bb_std", 2.0))
        atr_window      = int(self.params.get("atr_window", 10))
        stop_atr_mult   = float(self.params.get("stop_atr_mult", 1.2))
        target_atr_mult = float(self.params.get("target_atr_mult", 2.4))
        macd_fast       = int(self.params.get("macd_fast", 5))
        macd_slow       = int(self.params.get("macd_slow", 13))
        macd_signal     = int(self.params.get("macd_signal", 4))
        max_entries     = int(self.params.get("max_entries_per_symbol", 1))
        min_triggers    = int(self.params.get("min_triggers", 2))
        vol_mult        = float(self.params.get("vol_mult", 1.5))
        session_filter  = bool(self.params.get("session_filter", True))

        # ---------- OHLCV slicing ----------
        if isinstance(self.data.columns, pd.MultiIndex):
            close  = self.data.xs("close",  axis=1, level=1)
            high   = self.data.xs("high",   axis=1, level=1)
            low    = self.data.xs("low",    axis=1, level=1)
            open_  = self.data.xs("open",   axis=1, level=1)
            volume = self._get_volume(self.data, multi=True)
        else:
            close  = self.data["close"]
            high   = self.data["high"]
            low    = self.data["low"]
            open_  = self.data["open"]
            volume = self._get_volume(self.data, multi=False)

        # ---------- indicators ----------
        ema_f = align_columns(vbt.MA.run(close, ema_fast, ewm=True).ma, close)
        ema_m = align_columns(vbt.MA.run(close, ema_mid,  ewm=True).ma, close)
        ema_s = align_columns(vbt.MA.run(close, ema_slow, ewm=True).ma, close)

        rsi = align_columns(vbt.RSI.run(close, rsi_window).rsi, close)

        atr = self._compute_atr(high, low, close, atr_window)
        adx = self._compute_adx(high, low, close, adx_window)

        macd_obj  = vbt.MACD.run(
            close,
            fast_window=macd_fast,
            slow_window=macd_slow,
            signal_window=macd_signal,
        )
        macd_line = align_columns(macd_obj.macd,   close)
        macd_sig  = align_columns(macd_obj.signal, close)

        donchian_high = high.shift(1).rolling(donchian_window).max()

        bb_obj    = vbt.BBANDS.run(close, window=bb_window, alpha=bb_std)
        bb_lower  = align_columns(bb_obj.lower,  close)
        bb_middle = align_columns(bb_obj.middle, close)

        # ---------- volume filter ----------
        vol_ok = self._volume_filter(volume, vol_mult, close)

        # ---------- session-hour filter (NSE: skip open 30min + last 45min) ----------
        session_ok = self._session_filter(close.index, session_filter)

        # ---------- bias filter ----------
        ema_stack = (ema_f > ema_m) & (ema_m > ema_s)
        adx_strong = adx > adx_threshold
        if adx_must_rise:
            adx_slope = adx > adx.shift(1)
        elif isinstance(adx, pd.DataFrame):
            adx_slope = pd.DataFrame(True, index=adx.index, columns=adx.columns)
        else:
            adx_slope = pd.Series(True, index=adx.index)
        bias = ema_stack & adx_strong & adx_slope

        # ---------- entry triggers ----------
        # T1: MACD bullish cross
        t1 = (macd_line > macd_sig) & (macd_line.shift(1) <= macd_sig.shift(1))

        # T2: RSI oversold reversal (dipped within last 3 bars, now recovered)
        rsi_dipped    = (rsi.shift(1) < rsi_oversold) | (rsi.shift(2) < rsi_oversold) | (rsi.shift(3) < rsi_oversold)
        rsi_recovered = rsi > rsi_oversold
        t2 = rsi_dipped & rsi_recovered & (rsi > rsi.shift(1))

        # T3: Donchian breakout
        t3 = close > donchian_high

        # T4: Bollinger lower-band bounce
        touched_lower = (close.shift(1) <= bb_lower.shift(1)) | (low.shift(1) <= bb_lower.shift(1))
        t4 = touched_lower & (close > bb_middle.shift(1))

        # Count simultaneous triggers
        trigger_count = t1.astype(int) + t2.astype(int) + t3.astype(int) + t4.astype(int)
        enough_triggers = trigger_count >= min_triggers

        # Apply all filters
        entries = bias & enough_triggers & vol_ok & session_ok

        # ---------- trend-break exit ----------
        ema_break = (ema_f < ema_m) & (ema_f.shift(1) >= ema_m.shift(1))

        # ---------- bearish volume surge exit (institutional selling) ----------
        bear_vol = self._bear_volume_exit(volume, open_, close, vol_mult)

        combined_exit = ema_break | bear_vol

        # ---------- build exit frame ----------
        if isinstance(close, pd.DataFrame):
            exits = pd.DataFrame(False, index=close.index, columns=close.columns)
            for col in close.columns:
                exits[col] = self._exit_signals(
                    close[col], atr[col], entries[col], combined_exit[col],
                    stop_atr_mult, target_atr_mult, max_entries,
                )
        else:
            exits = self._exit_signals(
                close, atr, entries, combined_exit,
                stop_atr_mult, target_atr_mult, max_entries,
            )

        entries = entries.fillna(False).astype(bool)
        exits   = exits.fillna(False).astype(bool)

        return entries, exits

    # ------------------------------------------------------------------
    # Filter helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_volume(data, multi: bool):
        try:
            if multi:
                return data.xs("volume", axis=1, level=1)
            return data["volume"]
        except (KeyError, Exception):
            return None

    @staticmethod
    def _volume_filter(volume, vol_mult: float, close) -> "pd.DataFrame | pd.Series":
        """Return True where volume confirms entry (or vol disabled / unavailable)."""
        all_true = pd.DataFrame(True, index=close.index, columns=close.columns) if isinstance(close, pd.DataFrame) else pd.Series(True, index=close.index)
        if volume is None or vol_mult <= 0:
            return all_true
        try:
            vol_avg = volume.rolling(20).mean()
            return volume > vol_mult * vol_avg
        except Exception:
            return all_true

    @staticmethod
    def _bear_volume_exit(volume, open_, close, vol_mult: float) -> "pd.DataFrame | pd.Series":
        """Bearish volume surge: volume > 2x avg AND candle closes below open."""
        if isinstance(close, pd.DataFrame):
            all_false = pd.DataFrame(False, index=close.index, columns=close.columns)
        else:
            all_false = pd.Series(False, index=close.index)
        if volume is None or vol_mult <= 0:
            return all_false
        try:
            vol_avg = volume.rolling(20).mean()
            bear_candle = close < open_
            big_vol = volume > 2.0 * vol_avg
            return bear_candle & big_vol
        except Exception:
            return all_false

    @staticmethod
    def _session_filter(index: pd.DatetimeIndex, enabled: bool) -> "pd.Series":
        """
        NSE session filter: allow entries only between 09:45 and 14:45 IST.
        Skips opening auction noise (first 30 min) and closing volatility.
        Works even if index is timezone-naive (assumes IST).
        """
        allow = pd.Series(True, index=index)
        if not enabled:
            return allow
        try:
            # Handle tz-aware and tz-naive indexes
            if index.tz is not None:
                ist = index.tz_convert("Asia/Kolkata")
            else:
                ist = index
            time_minutes = ist.hour * 60 + ist.minute
            # 09:45 = 585 min, 14:45 = 885 min
            allow = pd.Series((time_minutes >= 585) & (time_minutes <= 885), index=index)
        except Exception:
            pass
        return allow

    # ------------------------------------------------------------------
    # Indicator helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_atr(high, low, close, window):
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low  - prev_close).abs()

        if isinstance(tr1, pd.DataFrame):
            tr = pd.concat([tr1, tr2, tr3]).groupby(level=0).max()
        else:
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        return tr.ewm(alpha=1 / window, adjust=False).mean()

    @staticmethod
    def _compute_adx(high, low, close, window):
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low  - prev_close).abs()

        if isinstance(tr1, pd.DataFrame):
            tr = pd.concat([tr1, tr2, tr3]).groupby(level=0).max()
        else:
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        up_move   = high.diff()
        down_move = -low.diff()

        plus_dm  = up_move.where((up_move > down_move)   & (up_move   > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        atr_v    = tr.ewm(alpha=1 / window, adjust=False).mean()
        plus_di  = 100 * plus_dm.ewm( alpha=1 / window, adjust=False).mean() / atr_v.replace(0, np.nan)
        minus_di = 100 * minus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr_v.replace(0, np.nan)

        dx  = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / window, adjust=False).mean()
        return adx.fillna(0)

    # ------------------------------------------------------------------
    # Exit logic
    # ------------------------------------------------------------------

    @staticmethod
    def _exit_signals(
        prices: pd.Series,
        atrs: pd.Series,
        entries: pd.Series,
        trend_break: pd.Series,
        stop_mult: float,
        target_mult: float,
        max_entries: int = 1,
    ) -> pd.Series:
        """
        ATR trailing stop + ATR profit target + trend-break exits.

        - Tracks multiple open positions (one per pyramid entry).
        - Caps concurrent entries at max_entries.
        - Exits fire on bar i+1 (next open) — no look-ahead bias.
        - Cooldown: 3 bars after any exit before re-entry (scaled for intraday).
        """
        exits        = pd.Series(False, index=prices.index)
        positions    = []
        pending_exit = False
        cooldown     = 0

        for i in range(len(prices)):
            price       = prices.iloc[i]
            atr_v       = atrs.iloc[i] if not pd.isna(atrs.iloc[i]) else 0.0
            broke       = bool(trend_break.iloc[i])

            if pending_exit:
                if i > 0:
                    exits.iloc[i] = True
                pending_exit = False
                positions.clear()
                cooldown = 3   # 3-bar cooldown (45 min on 15m, 3h on 1h)
                continue

            if cooldown > 0:
                cooldown -= 1

            if positions:
                new_positions = []
                triggered     = False

                for ep, peak, ea in positions:
                    peak          = max(peak, price)
                    trailing_stop = peak - stop_mult  * ea
                    target_price  = ep   + target_mult * ea

                    if price >= target_price or price <= trailing_stop or broke:
                        triggered = True
                    else:
                        new_positions.append((ep, peak, ea))

                if triggered:
                    pending_exit = True
                    positions    = new_positions
                    continue

            if (
                bool(entries.iloc[i])
                and atr_v > 0
                and len(positions) < max_entries
                and not pending_exit
                and cooldown == 0
            ):
                positions.append((price, price, atr_v))

        return exits
