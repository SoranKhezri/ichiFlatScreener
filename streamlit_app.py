# streamlit_app.py

import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# —————————————————————————————
# 1) Settings
SYMBOLS    = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT"]
TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

FLAT_LEN = 3    # bars to define a “flat”
LOOK_FWD = 51   # look‐forward window in bars

# —————————————————————————————
# 2) Fetch OHLCV from Bitunix public Spot K-Line endpoint
def fetch_ohlcv_bitunix(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    GET https://openapi.bitunix.com
    public interface – no API key required.
    Returns DataFrame indexed by ts with columns open, high, low, close, (volume if present).
    """
    url = "https://openapi.bitunix.com"
    params = {
        "symbol":   symbol.replace("/", ""),  # e.g. "BTCUSDT"
        "interval": interval,                 # "1m","5m","15m","1h","4h","1d"
        "limit":    limit,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data") or []
    if not data:
        raise ValueError(f"No data returned for {symbol}@{interval}")
    df = pd.DataFrame(data)
    # the returned fields per item: symbol, open, high, low, close, ts (ISO8601 string) 
    # (maybe volume if available)
    # parse timestamp
    df["ts"] = pd.to_datetime(df["ts"])
    df.set_index("ts", inplace=True)
    # ensure numeric columns
    for col in ("open","high","low","close","volume"):
        if col in df.columns:
            df[col] = df[col].astype(float)
    # if volume missing, fill with NaN
    if "volume" not in df.columns:
        df["volume"] = pd.NA
    return df[["open","high","low","close","volume"]]

# —————————————————————————————
# 3) Ichimoku Flat–Hit detection
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

    # look-forward window from each anchor timestamp
    for ts in anchor[anchor].index:
        end_ts = ts + timedelta(
            minutes=LOOK_FWD * (df.index.freq.delta.seconds / 60)
        )
        window = df.loc[ts:end_ts]
        if ((window["high"] >= kijun.loc[ts]) & (window["low"] <= kijun.loc[ts])).any():
            return True
    return False

# —————————————————————————————
# 4) Streamlit UI
st.set_page_config(page_title="Ichimoku Flat–Hit Scanner", layout="wide")
st.title("🔍 Ichimoku Flat–Hit Scanner")
st.markdown(f"- Scanning **{len(SYMBOLS)}** symbols × **{len(TIMEFRAMES)}** timeframes")

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
        pivot = df_res.pivot(index="symbol", columns="tf", values="signal").fillna("")
        st.dataframe(pivot, use_container_width=True)

    st.write(f"Last run: {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC")
else:
    st.info("Press **Run Scan now** to start scanning.")
