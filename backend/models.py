from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class BacktestRequest(BaseModel):
    strategy_name: str
    symbols: List[str]
    timeframe: str = "D"
    start_date: str = "2023-01-01"
    end_date: str = "2023-12-31"
    initial_capital: float = 50000.0
    params: Dict[str, Any] = {}

class BacktestResponse(BaseModel):
    metrics: Dict[str, Any]
    charts: Dict[str, Any]
    trades: List[Dict[str, Any]]
