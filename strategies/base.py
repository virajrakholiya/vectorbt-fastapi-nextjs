from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, data: pd.DataFrame, params: dict = None):
        self.data = data
        self.params = params or {}
        
    @abstractmethod
    def generate_signals(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Must return (entries, exits) DataFrames with boolean flags.
        """
        pass
