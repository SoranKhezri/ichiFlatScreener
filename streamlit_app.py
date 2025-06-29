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

API_KEY    = os.environ["BITUNIX_API_KEY"]
API_SECRET = os.environ["BITUNIX_API_SECRET"]

FLAT_LEN = 3    # bars for flat
LOOK_FWD = 51   # look-forward window (bars)

# —————————————————————————————
# 2) Fetch OHLCV from BitUnix REST API
def fetch_ohlcv_bitunix(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    Calls https://fapi.bitunix.com/spot/market/kline
    Returns DataFrame indexed by timestamp with open, high, low, close, volume.
    """
    url = "https://fapi.bitunix.com/spot/market/kline"
    headers = {
        "api-key":    API_KEY,
        "api-secret": API_SECRET,
    }
    params = {
        "symbol":   symbol.replace("/", ""),  # e.g. "BTCUSDT"
        "interval": interval,                 # e.g. "1m", "1h", "1d"
        "limit":    limit,
    }
    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    data = res.json()  # expect list of dicts with openTime, open, high, low, close, volume
    df = pd.DataFrame(data)
    df["ts"] = pd.to_datetime(df["openTime"], unit="ms")
    df.set_index("ts", inplace=True)
    return df[["open", "high", "low", "close", "volume"]]

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

    hit = False
    for ts in anchor[anchor].index:
        window = df.loc[ts : ts + pd.Timedelta(
            minutes=LOOK_FWD * df.index.freq.delta.seconds/60
        )]
        if ((window["high"] >= kijun[ts]) & (window["low"] <= kijun[ts])).any():
            hit = True
            break
    return hit

# —————————————————————————————
# 4) Streamlit UI
st.set_page_config(page_title="Ichimoku Flat–Hit Scanner", layout="wide")
st.title("🔍 Ichimoku Flat–Hit Scanner")
st.write(f"Scanning {len(SYMBOLS)} symbols × {len(TIMEFRAMES)} timeframes")

if st.button("🔄 Run Scan now"):
    results = []
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                df = fetch_ohlcv_bitunix(sym, tf, limit=200)
            except Exception as e:
                st.error(f"Error fetching {sym} @ {tf}: {e}")
                continue
            hit = calc_flat_hit(df)
            results.append({"symbol": sym, "tf": tf, "signal": "✔" if hit else ""})

    df_res = pd.DataFrame(results)
    if df_res.empty:
        st.warning("No data or all fetches failed.")
    else:
        pivot = df_res.pivot("symbol", "tf", "signal").fillna("")
        st.dataframe(pivot, use_container_width=True)

    st.write(f"Last run: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
else:
    st.info("Press **Run Scan now** to start scanning.")
