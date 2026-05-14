# Feature Specification: Intraday Mode & Leverage

## Goal
Add an "Intraday Mode" toggle to the backtesting dashboard. When enabled, it applies standard Indian broker rules:
1. **Leverage:** Users can choose leverage (typically up to 5x for intraday stocks in India).
2. **Brokerage:** Applies a fixed fee of ₹20 for entering and ₹20 for exiting a trade (Total ₹40 per round trip).

## Backend Changes

### 1. Data Model (`backend/models.py`)
Add new fields to `BacktestRequest`:
- `intraday_mode`: `bool` (default `False`)
- `leverage`: `float` (default `1.0`)

### 2. Backtest Engine (`backend/engine.py`)
Update the `BacktestEngine.run()` method to pass these parameters to VectorBT:
- If `intraday_mode` is True:
    - Pass `leverage=request.leverage` to `vbt.Portfolio.from_signals`.
    - Pass `fees=20.0` and `fixed_fees=True` (or similar VectorBT configuration for per-trade absolute fees).
    - *Note:* VectorBT's `fees` parameter usually handles percentage. For absolute ₹20, we may need to use `fixed_fees` or manual adjustment in the portfolio settings.

## Frontend Changes

### 1. Dashboard UI (`frontend/app/page.tsx`)
- Add a Section for **Trade Settings**.
- **Toggle:** "Intraday Mode".
- **Slider:** "Leverage" (Visible only when Intraday Mode is ON, range 1x to 5x).
- **Display:** Show a tooltip explaining the ₹20+₹20 brokerage logic.

### 2. API Integration
Update the `runBacktest` function in `page.tsx` to include `intraday_mode` and `leverage` in the POST request body.

## Implementation Steps
1. Update `backend/models.py`.
2. Update `backend/engine.py` logic.
3. Add UI controls in `frontend/app/page.tsx`.
4. Test with `IntradayScalperStrategy` to ensure the "Net Profit" reflects the brokerage costs.
