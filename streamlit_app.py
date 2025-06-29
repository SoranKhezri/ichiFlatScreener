# streamlit_app.py

import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime

# —————————————————————————————
# 1) Settings
SYMBOLS    = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT"]
TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

# (API-Key/Secret لازم نیست مگر برای private endpoints)
# API_KEY    = os.environ.get("BITUNIX_API_KEY", "")
# API_SECRET = os.environ.get("BITUNIX_API_SECRET", "")
API_KEY    = "7552c5d6c43d357a0308a220abdc7ab2"
API_SECRET = "e3bbd077fec52bf301f78838ecf51a6e"

FLAT_LEN = 3    # bars to define flat
LOOK_FWD = 51   # look-forward window in bars

# —————————————————————————————
# 2) Fetch OHLCV from Bitunix Spot API
def fetch_ohlcv_bitunix(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    Public spot kline endpoint:
      GET https://api.bitunix.com/api/spot/v1/market/kline
    params:
      symbol:   e.g. "BTCUSDT"
      interval: "1m","5m","15m","1h","4h","1d"
      limit:    up to 500
    returns DataFrame indexed by ts with open, high, low, close, volume
    """
    url = "https://api.bitunix.com/api/spot/v1/market/kline"
    headers = {
        # اگر این endpoint نیاز به auth داشته باشد، uncomment:
        # "X-API-KEY":    API_KEY,
        # "X-API-SECRET": API_SECRET,
    }
    params = {
        "symbol":   symbol.replace("/", ""),  # BTCUSDT
        "interval": interval,
        "limit":    limit,
    }
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data", [])
    if not data:
        raise ValueError(f"No data returned for {symbol}@{interval}")
    df = pd.DataFrame(data)
    # some fields may be string, cast:
    for col in ("open","high","low","close","volume"):
        if col in df.columns:
            df[col] = df[col].astype(float)
    # timestamp:
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"])
    elif "time" in df.columns:
        df["ts"] = pd.to_datetime(df["time"], unit="ms")
    else:
        df["ts"] = pd.to_datetime(df["openTime"], unit="ms")
    df.set_index("ts", inplace=True)
    # keep only necessary cols
    cols = [c for c in ("open","high","low","close","volume") if c in df.columns]
    return df[cols]

# —————————————————————————————
# 3) Ichimoku Flat–Hit logic
def calc_flat_hit(df: pd.DataFrame) -> bool:
    high26  = df["high"].rolling(26).max()
    low26   = df["low"].rolling(26).min()
    kijun   = (high26 + low26) / 2

    high52  = df["high"].rolling(52).max()
    low52   = df["low"].rolling(52).min()
    senkouB = (high52 + low52) / 2

    flat_k = kijun.diff().abs().rolling(FLAT_LEN).max() == 0
    flat_s = senkouB.diff().abs().rolling(FLAT_LEN).max() == 0
    same   = kijun == senkouB
    anchor = flat_k & flat_s & same

    for ts in anchor[anchor].index:
        window = df.loc[ts : ts + pd.Timedelta(
            minutes=LOOK_FWD * (df.index.freq.delta.seconds / 60)
        )]
        if ((window["high"] >= kijun[ts]) & (window["low"] <= kijun[ts])).any():
            return True
    return False

# —————————————————————————————
# 4) Streamlit UI
st.set_page_config(page_title="Ichimoku Flat–Hit Scanner", layout="wide")
st.title("🔍 Ichimoku Flat–Hit Scanner")
st.write(f"Scanning **{len(SYMBOLS)}** symbols × **{len(TIMEFRAMES)}** timeframes")

if st.button("🔄 Run Scan now"):
    results = []
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                df = fetch_ohlcv_bitunix(sym, tf, limit=200)
            except Exception as e:
                st.error(f"Error fetching {sym}@{tf}: {e}")
                continue
            hit = calc_flat_hit(df)
            results.append({"symbol": sym, "tf": tf, "signal": "✔" if hit else ""})

    df_res = pd.DataFrame(results)
    if df_res.empty:
        st.warning("No data or all fetches failed.")
    else:
        pivot = df_res.pivot("symbol", "tf", "signal").fillna("")
        st.dataframe(pivot, use_container_width=True)
    st.write(f"Last run: {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC")
else:
    st.info("Press **Run Scan now** to start scanning.")
