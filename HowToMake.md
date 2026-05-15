# How to Build a Strategy — Template for AI Agents

This guide is a complete reference for adding a new strategy to this VectorBT + FastAPI + Next.js backtesting framework. Follow every section in order.

---

## 1. Architecture Snapshot

```
vectorBT/
├── backend/
│   ├── main.py          ← route handler + STRATEGY_MAP + STRATEGY_META
│   ├── engine.py        ← runs vbt.Portfolio.from_signals(), extracts metrics
│   ├── fyers_client.py  ← fetches OHLCV (Fyers API or yfinance fallback)
│   └── models.py        ← Pydantic request/response models
├── strategies/
│   ├── base.py          ← BaseStrategy (abstract)
│   ├── pro_trader.py    ← example daily strategy
│   └── intraday_scalper.py  ← example intraday strategy
└── frontend/
    └── app/page.tsx     ← single-page UI, reads /api/strategies + /api/backtest
```

Data flows: `BacktestRequest` → `DataFetcher` → `Strategy.generate_signals()` → `BacktestEngine.run()` → `BacktestResponse`.

---

## 2. Strategy File Template

Create `strategies/my_strategy.py`. Every strategy must:

- Extend `BaseStrategy`
- Implement `generate_signals()` returning `(entries, exits)` — both boolean DataFrames
- Set `accumulate` and `entry_size` class attributes

```python
from .base import BaseStrategy, align_columns
import pandas as pd
import numpy as np
import vectorbt as vbt


class MyStrategy(BaseStrategy):
    """One-line description."""

    accumulate = False   # True = pyramiding allowed (multiple open positions)
    entry_size = 1.0     # fraction of available cash per entry (0.4 for 2-slot pyramid)

    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        # --- 1. Read parameters (always provide a default) ---
        fast = int(self.params.get("ema_fast", 9))
        slow = int(self.params.get("ema_slow", 21))

        # --- 2. Slice OHLC from self.data ---
        # self.data is ALWAYS a MultiIndex DataFrame: columns = (symbol, field)
        # even when only one symbol is requested.
        if isinstance(self.data.columns, pd.MultiIndex):
            close = self.data.xs("close", axis=1, level=1)
            high  = self.data.xs("high",  axis=1, level=1)
            low   = self.data.xs("low",   axis=1, level=1)
        else:
            # Defensive fallback — should not happen in production
            close = self.data["close"]
            high  = self.data["high"]
            low   = self.data["low"]

        # --- 3. Compute indicators ---
        # ALWAYS wrap vbt indicator output with align_columns() before boolean ops.
        # VectorBT may return a slightly different column index; align_columns() fixes it.
        ema_f = align_columns(vbt.MA.run(close, fast, ewm=True).ma, close)
        ema_s = align_columns(vbt.MA.run(close, slow, ewm=True).ma, close)
        rsi   = align_columns(vbt.RSI.run(close, 14).rsi, close)

        # --- 4. Build entry and exit signals (boolean DataFrames) ---
        entries = (ema_f > ema_s) & (rsi < 70)
        exits   = ema_f < ema_s

        # --- 5. Clean up NaNs ---
        entries = entries.fillna(False).astype(bool)
        exits   = exits.fillna(False).astype(bool)

        return entries, exits
```

### `align_columns()` — why it exists

VectorBT indicator `.ma`, `.rsi`, etc. can carry a tuple column name `(window, symbol)` instead of plain `symbol`. `align_columns(indicator_df, close)` resets indicator columns to match `close` columns so boolean operations (`>`, `&`) don't produce all-NaN results.

```python
# BAD — may silently produce all NaN
entries = vbt.MA.run(close, 9, ewm=True).ma > close

# GOOD
ema = align_columns(vbt.MA.run(close, 9, ewm=True).ma, close)
entries = ema > close
```

---

## 3. self.data Contract

| Property | Type | Notes |
|----------|------|-------|
| `self.data` | `pd.DataFrame` | Always MultiIndex columns `(symbol, field)` |
| `self.params` | `dict` | Keys are param `name` strings from STRATEGY_META |

Field names in `self.data`: `open`, `high`, `low`, `close`, `volume` (lowercase).

Access patterns:
```python
# All symbols, one field
close = self.data.xs("close", axis=1, level=1)   # DataFrame, cols = symbols

# One symbol, all fields  (useful inside loops)
sym_df = self.data["RELIANCE"]                    # DataFrame, cols = fields

# Single cell (last close of RELIANCE)
price = self.data["RELIANCE"]["close"].iloc[-1]
```

---

## 4. Common Indicator Patterns

### ATR
```python
prev_close = close.shift(1)
tr = pd.concat([high - low,
                (high - prev_close).abs(),
                (low  - prev_close).abs()]).groupby(level=0).max()
atr = tr.ewm(alpha=1/14, adjust=False).mean()
```

### MACD cross
```python
macd_obj  = vbt.MACD.run(close, fast_window=12, slow_window=26, signal_window=9)
macd_line = align_columns(macd_obj.macd,   close)
macd_sig  = align_columns(macd_obj.signal, close)
cross_up   = (macd_line > macd_sig) & (macd_line.shift(1) <= macd_sig.shift(1))
```

### Donchian breakout (no look-ahead)
```python
# shift(1) so today's close is not included in the window
donchian_high = high.shift(1).rolling(20).max()
breakout = close > donchian_high
```

### Bollinger Bands
```python
bb = vbt.BBANDS.run(close, window=20, alpha=2.0)
bb_upper  = align_columns(bb.upper,  close)
bb_lower  = align_columns(bb.lower,  close)
bb_middle = align_columns(bb.middle, close)
```

---

## 5. Exit Signal Patterns

VectorBT `from_signals()` exits the *entire* position when `exits=True` on a bar. Two approaches:

### A. Vectorised (fast, no loop)
Works when exit condition doesn't depend on entry price.
```python
exits = ema_f < ema_s   # EMA cross-down
```

### B. Iterative (needed for ATR stops, profit targets)
Loop over bars, track open positions, set `exits.iloc[i] = True`.
```python
exits = pd.Series(False, index=prices.index)
positions = []   # list of (entry_price, peak, entry_atr)
for i in range(len(prices)):
    price = prices.iloc[i]
    atr_v = atrs.iloc[i]
    if positions:
        new_pos = []
        triggered = False
        for ep, peak, ea in positions:
            peak = max(peak, price)
            if price <= peak - stop_mult * ea or price >= ep + target_mult * ea:
                triggered = True
            else:
                new_pos.append((ep, peak, ea))
        if triggered:
            exits.iloc[i] = True
            positions = new_pos
    if bool(entries.iloc[i]) and atr_v > 0:
        positions.append((price, price, atr_v))
```

**Look-ahead bias rule:** Never use `close.iloc[i]` to make a decision and then set an entry/exit on the *same* bar `i`. Either shift signals by 1, or set a `pending` flag and fire on `i+1`.

---

## 6. Pyramiding Rules

To allow multiple entries into the same symbol:
```python
accumulate = True
entry_size = 0.4    # 2 × 0.4 = 0.8 of capital; leaves room for 2 positions
```

With `accumulate=True`, VectorBT allows multiple buys on the same symbol. The engine calls `Portfolio.from_signals(..., accumulate=True)`.

**Pyramid only on profit** (avoids averaging down):
```python
if entries.iloc[i] and positions:
    last_ep = positions[-1][0]
    if price < last_ep + pyramid_min_atr * atr_v:
        continue   # skip — price hasn't moved enough
```

---

## 7. Register the Strategy

### 7a. `backend/main.py` — add to STRATEGY_MAP
```python
from strategies.my_strategy import MyStrategy

STRATEGY_MAP = {
    "pro_trader":       ProTraderStrategy,
    "intraday_scalper": IntradayScalperStrategy,
    "my_strategy":      MyStrategy,          # ← add here
}
```

### 7b. `backend/main.py` — add to STRATEGY_META
Every key in `params` must match exactly a `self.params.get("key", default)` call inside the strategy. No orphan params.

```python
STRATEGY_META = {
    ...
    "my_strategy": {
        "label": "My Strategy (short display name)",
        "description": "One paragraph shown in the UI.",
        "params": [
            # Required fields: name, label, type, default, min, max
            # Optional: step (for float sliders)
            {"name": "ema_fast",  "label": "EMA Fast",  "type": "number", "default": 9,  "min": 2,  "max": 50},
            {"name": "ema_slow",  "label": "EMA Slow",  "type": "number", "default": 21, "min": 5,  "max": 200},
            {"name": "stop_mult", "label": "Stop Mult", "type": "number", "default": 1.5,"min": 0.5,"max": 5.0, "step": 0.1},
        ],
    },
}
```

**Rule:** Keep STRATEGY_META params in sync with what the strategy reads. Remove any param the strategy ignores. Add any param the strategy reads.

---

## 8. Supported Timeframes

| Value | Description | Use case |
|-------|-------------|----------|
| `"1D"` | Daily | Swing/position strategies |
| `"1W"` | Weekly | Long-term trend |
| `"60"` | 1-hour | Intraday |
| `"30"` | 30-min | Intraday |
| `"15"` | 15-min | Scalping |
| `"5"` | 5-min | Scalping |

For intraday strategies, set `request.intraday_mode=True` in the engine call. This affects:
- Fee model (currently `fixed_fees=20.0` per leg — ₹40/trade)
- Frequency annualisation for Sharpe

**Warning:** Do NOT run a daily-bar strategy (pro_trader) on intraday timeframes. ADX/EMA indicators need hundreds of bars of warm-up; intraday bars produce noisy signals and fee drag compounds catastrophically.

---

## 9. Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Missing `align_columns()` | All signals NaN, 0 trades | Wrap every vbt indicator output |
| Same-bar look-ahead | Unrealistically high returns in backtest | Use `shift(1)` on signals or pending-exit pattern |
| `exit_size` not set | Partial position remains open | VectorBT defaults to full exit on sell signal |
| Orphan params in META | UI shows slider but strategy ignores it | Keep META ↔ `self.params.get()` in sync |
| `accumulate=True` with `entry_size=1.0` | Second entry fails (no cash left) | Use `entry_size = 1 / max_entries` |
| Intraday + high fixed fee | Fees > gross profit, strategy appears useless | Lower `fixed_fees` or use percentage fee |
| `freq="D"` in engine on intraday | Sharpe ratio wrong (over-annualised) | Engine needs `freq` proportional to bar size |
| NaN in signal DataFrame | VectorBT counts NaN as False — silent, OK | `fillna(False).astype(bool)` before returning |

---

## 11. Full Minimal Example

```python
# strategies/ema_crossover.py
from .base import BaseStrategy, align_columns
import pandas as pd
import vectorbt as vbt


class EMACrossoverStrategy(BaseStrategy):
    accumulate = False
    entry_size = 1.0

    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        fast = int(self.params.get("ema_fast", 9))
        slow = int(self.params.get("ema_slow", 21))

        if isinstance(self.data.columns, pd.MultiIndex):
            close = self.data.xs("close", axis=1, level=1)
        else:
            close = self.data["close"]

        ema_f = align_columns(vbt.MA.run(close, fast, ewm=True).ma, close)
        ema_s = align_columns(vbt.MA.run(close, slow, ewm=True).ma, close)

        entries = (ema_f > ema_s) & (ema_f.shift(1) <= ema_s.shift(1))
        exits   = (ema_f < ema_s) & (ema_f.shift(1) >= ema_s.shift(1))

        return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)
```

Register in `main.py`:
```python
from strategies.ema_crossover import EMACrossoverStrategy
STRATEGY_MAP["ema_crossover"] = EMACrossoverStrategy
STRATEGY_META["ema_crossover"] = {
    "label": "EMA Crossover",
    "description": "Classic dual EMA crossover.",
    "params": [
        {"name": "ema_fast", "label": "EMA Fast", "type": "number", "default": 9,  "min": 2,  "max": 50},
        {"name": "ema_slow", "label": "EMA Slow", "type": "number", "default": 21, "min": 5, "max": 200},
    ],
}
```

Done. The strategy appears in the frontend dropdown automatically.
