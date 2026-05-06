from .base import BaseStrategy
import pandas as pd
import vectorbt as vbt

class SMACrossoverStrategy(BaseStrategy):
    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        fast_window = int(self.params.get('fast_window', 10))
        slow_window = int(self.params.get('slow_window', 50))
        
        if isinstance(self.data.columns, pd.MultiIndex):
            close_prices = self.data.xs('close', axis=1, level=1)
        else:
            close_prices = self.data['close']
            
        fast_sma = vbt.MA.run(close_prices, fast_window)
        slow_sma = vbt.MA.run(close_prices, slow_window)
        
        entries = fast_sma.ma_crossed_above(slow_sma)
        exits = fast_sma.ma_crossed_below(slow_sma)
        
        return entries, exits
