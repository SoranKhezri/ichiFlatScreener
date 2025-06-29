import ccxt, pandas as pd, streamlit as st
from datetime import datetime

# — پارامترها
SYMBOLS  = ["BTC/USDT","ETH/USDT","BNB/USDT","XRP/USDT"]  # تا 100 تایی کنید
TIMEFRAMES = ["1m","5m","15m","1h","4h","1d"]
FLAT_LEN = 3
LOOK_FWD = 51

def calc_signals(df):
    high26  = df['high'].rolling(26).max()
    low26   = df['low'].rolling(26).min()
    kijun   = (high26 + low26) / 2
    high52  = df['high'].rolling(52).max()
    low52   = df['low'].rolling(52).min()
    senkouB = (high52 + low52) / 2

    flat_k = kijun.diff().abs().rolling(FLAT_LEN).max() == 0
    flat_s = senkouB.diff().abs().rolling(FLAT_LEN).max() == 0
    same   = kijun == senkouB
    anchor = flat_k & flat_s & same

    hit = False
    for idx in anchor[anchor].index:
        window = df.loc[idx: idx + pd.Timedelta(minutes=LOOK_FWD * df.index.freq.delta.seconds/60)]
        if ((window['high'] >= kijun[idx]) & (window['low'] <= kijun[idx])).any():
            hit = True
            break
    return hit

st.title("🔍 Ichimoku Flat–Hit Scanner")
st.write(f"Scan {len(SYMBOLS)} symbols × {len(TIMEFRAMES)} timeframes")

if st.button("🔄 Run Scan now"):

    # try Binance first, if it's geo-blocked switch to Bybit  
    import ccxt
    import os
    exchange = ccxt.bitunix({
        "apiKey": os.environ['BITUNIX_API_KEY'],
        "secret": os.environ['BITUNIX_API_SECRET'],
        "enableRateLimit": True,
    })
exchange.load_markets()
    
    results = []
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            ohlcv = exchange.fetch_ohlcv(sym, timeframe=tf, limit=200)
            df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','vol'])
            df.ts = pd.to_datetime(df.ts, unit='ms')
            df.set_index('ts', inplace=True)
            hit = calc_signals(df)
            results.append({"symbol": sym, "tf": tf, "signal": "✔" if hit else ""})
    df_res = pd.DataFrame(results)
    pivot = df_res.pivot("symbol", "tf", "signal").fillna("")
    st.dataframe(pivot)
    st.write(f"Last run: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
else:
    st.write("Press **Run Scan now** to start.")
