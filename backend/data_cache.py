"""
Disk-based OHLCV cache (Parquet, per symbol + timeframe).

Layout:
  backend/data/cache/{symbol}_{timeframe}.parquet

TTL:
  Daily / weekly / monthly  → 24 h
  Intraday (anything else)  → 1 h

Hit logic:
  1. File exists and is fresh (mtime < TTL)
  2. Cached index covers requested [start_date, end_date]
  → return slice; else return None → caller fetches from API

Put logic:
  Load existing file (if any), concat new data, deduplicate, save.
  This grows the cache over time so partial fetches still benefit next run.
"""

import time
import pandas as pd
from pathlib import Path


_DAILY_TIMEFRAMES = {"1D", "D", "1W", "W", "1M", "M"}
_DAILY_TTL  = 86_400   # 24 h in seconds
_INTRADAY_TTL = 3_600  # 1 h in seconds


class DataCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def _path(self, symbol: str, timeframe: str) -> Path:
        safe = timeframe.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{symbol}_{safe}.parquet"

    def _ttl(self, timeframe: str) -> int:
        return _DAILY_TTL if timeframe in _DAILY_TIMEFRAMES else _INTRADAY_TTL

    # ------------------------------------------------------------------
    def get(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """
        Return cached DataFrame slice for symbol+timeframe+date range,
        or None on cache miss / stale / insufficient coverage.
        """
        path = self._path(symbol, timeframe)
        if not path.exists():
            return None

        age = time.time() - path.stat().st_mtime
        if age > self._ttl(timeframe):
            print(f"[cache] STALE  {symbol} {timeframe} (age {age/60:.0f} min)")
            return None

        try:
            df = pd.read_parquet(path)
        except Exception as e:
            print(f"[cache] READ ERROR {path}: {e}")
            return None

        if df.empty:
            return None

        # Normalise index to tz-naive for comparison
        idx = df.index
        if idx.tz is not None:
            idx = idx.tz_localize(None)
            df.index = idx

        req_start = pd.Timestamp(start_date)
        req_end   = pd.Timestamp(end_date)

        if idx.min() > req_start or idx.max() < req_end:
            print(
                f"[cache] PARTIAL {symbol} {timeframe} "
                f"(have {idx.min().date()}..{idx.max().date()}, "
                f"need {req_start.date()}..{req_end.date()})"
            )
            return None

        print(f"[cache] HIT    {symbol} {timeframe}")
        return df.loc[req_start:req_end]

    # ------------------------------------------------------------------
    def put(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        """Merge df into existing cache file and save."""
        if df is None or df.empty:
            return

        path = self._path(symbol, timeframe)

        # Drop tz info so concat is always tz-naive
        df = df.copy()
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        if path.exists():
            try:
                existing = pd.read_parquet(path)
                if existing.index.tz is not None:
                    existing.index = existing.index.tz_localize(None)
                df = pd.concat([existing, df]).sort_index()
                df = df[~df.index.duplicated(keep="last")]
            except Exception as e:
                print(f"[cache] MERGE ERROR {path}: {e}")

        try:
            df.to_parquet(path)
            print(f"[cache] SAVED  {symbol} {timeframe}  rows={len(df)}")
        except Exception as e:
            print(f"[cache] WRITE ERROR {path}: {e}")
