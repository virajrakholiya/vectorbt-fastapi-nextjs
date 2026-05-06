from abc import ABC, abstractmethod
import pandas as pd


def align_columns(indicator_df, reference):
    """
    Strip indicator-parameter levels added by vectorBT so columns match close_prices.
    vbt.MA.run(close, 10).ma has columns like (10, 'INFY') — this drops the extra level.
    """
    if isinstance(indicator_df, pd.DataFrame) and isinstance(indicator_df.columns, pd.MultiIndex):
        indicator_df = indicator_df.copy()
        if isinstance(reference, pd.DataFrame):
            indicator_df.columns = reference.columns
        else:
            indicator_df = indicator_df.iloc[:, 0]
    return indicator_df

class BaseStrategy(ABC):
    # Override to enable position pyramiding (multiple entries add to position)
    accumulate: bool = False
    # Per-entry position size (0.0-1.0 = percent of available capital)
    entry_size: float = 1.0

    def __init__(self, data: pd.DataFrame, params: dict = None):
        self.data = data
        self.params = params or {}

    @abstractmethod
    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Must return (entries, exits) DataFrames with boolean flags.
        """
        pass
