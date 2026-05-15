import pandas as pd
import yfinance as yf
from fyers_apiv3 import fyersModel
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# FYERS API limits per resolution (in days)
_FYERS_MAX_DAYS = {
    "1D": 366,
    "1W": 366,
    "1M": 366,
}
_FYERS_INTRADAY_MAX_DAYS = 100  # for minute resolutions


def _chunk_date_ranges(start_date: str, end_date: str, max_days: int):
    """Split a date range into chunks of at most max_days each."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    chunks = []
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=max_days - 1), end)
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + timedelta(days=1)
    return chunks

class DataFetcher:
    def __init__(self):
        # Load .env from backend directory regardless of CWD
        backend_dir = Path(__file__).resolve().parent
        env_path = backend_dir / ".env"
        load_dotenv(dotenv_path=env_path)

        self.fyers_app_id = os.getenv("FYERS_APP_ID")
        self.fyers_access_token = os.getenv("FYERS_ACCESS_TOKEN")
        self.use_fyers = bool(self.fyers_app_id and self.fyers_access_token)

        if self.use_fyers:
            # FyersModel requires log_path directory to exist; create absolute path
            log_dir = backend_dir / "data"
            log_dir.mkdir(parents=True, exist_ok=True)
            # FyersModel concatenates log_path + "fyersApi.log" so trailing separator required
            log_path_str = str(log_dir) + os.sep

            self.fyers = fyersModel.FyersModel(
                client_id=self.fyers_app_id,
                token=self.fyers_access_token,
                log_path=log_path_str,
            )
            
    def fetch_data(self, symbols: list, start_date: str, end_date: str, timeframe: str = "1D") -> pd.DataFrame:
        """
        Fetches OHLCV data. Falls back to yfinance if FYERS credentials are not set or fail.
        Returns a MultiIndex DataFrame if multiple symbols, else single Index DataFrame.
        """
        df = pd.DataFrame()
        if self.use_fyers:
            try:
                df = self._fetch_from_fyers(symbols, start_date, end_date, timeframe)
            except Exception as e:
                print(f"FYERS fetch failed: {e}")
        
        if df.empty:
            print("Falling back to yfinance...")
            df = self._fetch_from_yfinance(symbols, start_date, end_date, timeframe)
            
        return df

    def _fetch_from_fyers(self, symbols: list, start_date: str, end_date: str, timeframe: str) -> pd.DataFrame:
        print("Fetching data from FYERS API...")
        # FYERS mapping for timeframe
        res = "1D" if timeframe in ["D", "1D"] else timeframe

        # Determine max chunk size based on resolution
        if res in _FYERS_MAX_DAYS:
            max_days = _FYERS_MAX_DAYS[res]
        else:
            max_days = _FYERS_INTRADAY_MAX_DAYS

        date_chunks = _chunk_date_ranges(start_date, end_date, max_days)
        all_data = []

        for sym in symbols:
            sym_chunks = []
            for chunk_start, chunk_end in date_chunks:
                data = {
                    "symbol": f"NSE:{sym}-EQ",
                    "resolution": res,
                    "date_format": "1",
                    "range_from": chunk_start,
                    "range_to": chunk_end,
                    "cont_flag": "1",
                }
                response = self.fyers.history(data=data)

                if response.get("s") == "ok":
                    candles = response.get("candles", [])
                    if candles:
                        chunk_df = pd.DataFrame(
                            candles,
                            columns=["date", "open", "high", "low", "close", "volume"],
                        )
                        chunk_df["date"] = pd.to_datetime(chunk_df["date"], unit="s")
                        chunk_df.set_index("date", inplace=True)
                        sym_chunks.append(chunk_df)
                else:
                    print(f"Error fetching {sym} [{chunk_start}..{chunk_end}] from FYERS: {response}")

            if sym_chunks:
                df = pd.concat(sym_chunks).sort_index()
                df = df[~df.index.duplicated(keep="first")]
                df.columns = pd.MultiIndex.from_product([[sym], df.columns])
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        return pd.concat(all_data, axis=1)

    def _fetch_from_yfinance(self, symbols: list, start_date: str, end_date: str, timeframe: str) -> pd.DataFrame:
        print("FYERS credentials not found, falling back to yfinance...")
        # YFinance uses '.NS' suffix for NSE stocks
        yf_symbols = [f"{sym}.NS" for sym in symbols]
        
        # Mapping timeframe to yfinance interval strings
        _yf_map = {
            "D": "1d", "1D": "1d",
            "W": "1wk", "1W": "1wk",
            "M": "1mo", "1M": "1mo",
            "240": "60m", "180": "90m", "120": "60m",
            "60": "60m", "45": "30m", "30": "30m",
            "20": "15m", "15": "15m", "10": "5m",
            "5": "5m", "3": "2m", "2": "2m", "1": "1m",
        }
        interval = _yf_map.get(timeframe, timeframe)
        
        df = yf.download(yf_symbols, start=start_date, end=end_date, interval=interval)
        
        # YFinance returns columns as (Attribute, Ticker). We swap to match (Ticker, Attribute)
        # and remove '.NS' suffix
        if len(symbols) > 1:
            df = df.swaplevel(axis=1)
            df.columns = df.columns.set_levels([col.replace(".NS", "") for col in df.columns.levels[0]], level=0)
            df.columns = df.columns.set_names([None, None])
            df.sort_index(axis=1, inplace=True)
            # Make columns lowercase to match standard
            df.columns = pd.MultiIndex.from_tuples([(c[0], c[1].lower()) for c in df.columns])
        else:
            # Single symbol case
            sym = symbols[0]
            df.columns = [c.lower() for c in df.columns]
            df.columns = pd.MultiIndex.from_product([[sym], df.columns])
            
        return df
