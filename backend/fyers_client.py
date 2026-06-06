import pandas as pd
import yfinance as yf
from fyers_apiv3 import fyersModel
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from .data_cache import DataCache

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
        backend_dir = Path(__file__).resolve().parent
        env_path = backend_dir / ".env"
        load_dotenv(dotenv_path=env_path)

        self.fyers_app_id = os.getenv("FYERS_APP_ID")
        self.fyers_access_token = os.getenv("FYERS_ACCESS_TOKEN")
        self.use_fyers = bool(self.fyers_app_id and self.fyers_access_token)

        if self.use_fyers:
            log_dir = backend_dir / "data"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path_str = str(log_dir) + os.sep

            self.fyers = fyersModel.FyersModel(
                client_id=self.fyers_app_id,
                token=self.fyers_access_token,
                log_path=log_path_str,
            )

        cache_dir = backend_dir / "data" / "cache"
        self.cache = DataCache(cache_dir)

    # ------------------------------------------------------------------
    def fetch_data(
        self,
        symbols: list,
        start_date: str,
        end_date: str,
        timeframe: str = "1D",
    ) -> pd.DataFrame:
        """
        Return MultiIndex OHLCV DataFrame.
        Serves from disk cache when possible; fetches from API only on miss.
        Cache is per-symbol per-timeframe so changing timeframe still uses cache.
        """
        cached_sym_dfs: dict[str, pd.DataFrame] = {}
        to_fetch: list[str] = []

        for sym in symbols:
            hit = self.cache.get(sym, timeframe, start_date, end_date)
            if hit is not None:
                cached_sym_dfs[sym] = hit
            else:
                to_fetch.append(sym)

        if to_fetch:
            fetched_map = self._fetch_raw(to_fetch, start_date, end_date, timeframe)
            for sym, sym_df in fetched_map.items():
                self.cache.put(sym, timeframe, sym_df)
                # slice to requested range after caching full fetch
                idx = sym_df.index
                if idx.tz is not None:
                    idx = idx.tz_localize(None)
                    sym_df = sym_df.copy()
                    sym_df.index = idx
                s = pd.Timestamp(start_date)
                e = pd.Timestamp(end_date)
                cached_sym_dfs[sym] = sym_df.loc[s:e]

        if not cached_sym_dfs:
            return pd.DataFrame()

        all_dfs = []
        for sym, df in cached_sym_dfs.items():
            df = df.copy()
            df.columns = pd.MultiIndex.from_product([[sym], df.columns])
            all_dfs.append(df)

        return pd.concat(all_dfs, axis=1)

    # ------------------------------------------------------------------
    def _fetch_raw(
        self,
        symbols: list,
        start_date: str,
        end_date: str,
        timeframe: str,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch from FYERS (or yfinance fallback).
        Returns dict {symbol: single-level-OHLCV DataFrame}.
        """
        result: dict[str, pd.DataFrame] = {}

        if self.use_fyers:
            try:
                result = self._fetch_from_fyers(symbols, start_date, end_date, timeframe)
            except Exception as e:
                print(f"FYERS fetch failed: {e}")

        missing = [s for s in symbols if s not in result or result[s].empty]
        if missing:
            print(f"Falling back to yfinance for: {missing}")
            yf_result = self._fetch_from_yfinance(missing, start_date, end_date, timeframe)
            result.update(yf_result)

        return result

    # ------------------------------------------------------------------
    def _fetch_from_fyers(
        self, symbols: list, start_date: str, end_date: str, timeframe: str
    ) -> dict[str, pd.DataFrame]:
        print("Fetching data from FYERS API...")
        res = "1D" if timeframe in ["D", "1D"] else timeframe
        max_days = _FYERS_MAX_DAYS.get(res, _FYERS_INTRADAY_MAX_DAYS)
        date_chunks = _chunk_date_ranges(start_date, end_date, max_days)

        result: dict[str, pd.DataFrame] = {}

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
                    print(f"Error fetching {sym} [{chunk_start}..{chunk_end}]: {response}")

            if sym_chunks:
                df = pd.concat(sym_chunks).sort_index()
                df = df[~df.index.duplicated(keep="first")]
                result[sym] = df

        return result

    # ------------------------------------------------------------------
    def _fetch_from_yfinance(
        self, symbols: list, start_date: str, end_date: str, timeframe: str
    ) -> dict[str, pd.DataFrame]:
        print("Fetching from yfinance...")
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
        yf_symbols = [f"{sym}.NS" for sym in symbols]

        raw = yf.download(yf_symbols, start=start_date, end=end_date, interval=interval)

        result: dict[str, pd.DataFrame] = {}

        if len(symbols) == 1:
            sym = symbols[0]
            df = raw.copy()
            df.columns = [c.lower() for c in df.columns]
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            result[sym] = df
        else:
            # MultiIndex: (Attribute, Ticker) → swap to (Ticker, Attribute)
            raw = raw.swaplevel(axis=1)
            raw.columns = raw.columns.set_levels(
                [col.replace(".NS", "") for col in raw.columns.levels[0]], level=0
            )
            raw.columns = raw.columns.set_names([None, None])
            raw.sort_index(axis=1, inplace=True)
            raw.columns = pd.MultiIndex.from_tuples(
                [(c[0], c[1].lower()) for c in raw.columns]
            )
            if raw.index.tz is not None:
                raw.index = raw.index.tz_localize(None)

            for sym in symbols:
                try:
                    df = raw[sym].copy()
                    result[sym] = df
                except KeyError:
                    print(f"[yfinance] no data for {sym}")

        return result
