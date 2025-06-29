# streamlit_app.py

import os
import time, uuid, hmac, hashlib, urllib.parse
import requests
import pandas as pd
import streamlit as st
from datetime import datetime

# —————————————————————————————
# 1) Settings
SYMBOLS    = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT"]
TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

API_KEY    = "7552c5d6c43d357a0308a220abdc7ab2"
API_SECRET = "e3bbd077fec52bf301f78838ecf51a6e"

# اگر هنوز کلیدت را نذاشتی، اخطار بده و اجراتو متوقف کن
if not API_KEY or API_KEY.startswith("<PASTE"):
    raise RuntimeError("🔑 Please set BITUNIX_API_KEY & BITUNIX_API_SECRET either in env vars or directly in code")

FLAT_LEN = 3
LOOK_FWD = 51

# —————————————————————————————
# 2) Signature & Fetch
def bitunix_headers(params: dict) -> dict:
    """
    تولید هدرهای api-key, nonce, timestamp, sign
    """
    nonce     = uuid.uuid4().hex
    timestamp = str(int(time.time() * 1000))
    # مرتب‌سازی پارامترها و encode
    qs = urllib.parse.urlencode(sorted(params.items()))
    # طبق مستند: sign رشته nonce+timestamp+qs را با HMAC-SHA256 می‌سازد
    payload = f"{nonce}{timestamp}{qs}"
    sign = hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return {
        "api-key":    API_KEY,
        "nonce":      nonce,
        "timestamp":  timestamp,
        "sign":       sign,
        "Content-Type": "application/json",
    }

def fetch_ohlcv_bitunix(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    GET https://openapi.bitunix.com
    """
    base_url = "https://openapi.bitunix.com"
    params = {
        "symbol":   symbol.replace("/", ""),  # BTCUSDT
        "interval": interval,                 # 1m,5m,15m,1h,4h,1d
        "limit":    limit,
    }
    headers = bitunix_headers(params)
    resp = requests.get(base_url, headers=headers, params=params)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data", [])
    if not data:
        raise ValueError(f"No data for {symbol}@{interval}")
    df = pd.DataFrame(data)
    # فرض فیلدها: openTime, open, high, low, close, volume
    df["ts"] = pd.to_datetime(df["openTime"], unit="ms")
    df.set_index("ts", inplace=True)
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    return df[["open","high","low","close","volume"]]

# —————————————————————————————
# 3) Ichimoku Flat–Hit
def calc_flat_hit(df: pd.DataFrame) -> bool:
    h26 = df["high"].rolling(26).max()
    l26 = df["low"].rolling(26).min()
    kij = (h26 + l26) / 2
    h52 = df["high"].rolling(52).max()
    l52 = df["low"].rolling(52).min()
    sen = (h52 + l52) / 2

    flat_k = kij.diff().abs().rolling(FLAT_LEN).max() == 0
    flat_s = sen.diff().abs().rolling(FLAT_LEN).max() == 0
    anchor = flat_k & flat_s & (kij == sen)

    for ts in anchor[anchor].index:
        window = df.loc[ts : ts + pd.Timedelta(
            minutes=LOOK_FWD * df.index.freq.delta.seconds/60
        )]
        if ((window["high"] >= kij[ts]) & (window["low"] <= kij[ts])).any():
            return True
    return False

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
