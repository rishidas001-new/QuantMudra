#!/usr/bin/env python3
"""Nifty 500 + FNO Bulk Acquisition"""
import yfinance as yf
import pandas as pd
import oracledb
import time
import os
import sys

DB = {
    'user': 'admin', 
    'password': 'QuantMudra@2026', 
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet', 
    'wallet_password': 'QuantMudra@2026'
}

LOG_DIR = '/home/openhands/.oci/logs'
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = f"{LOG_DIR}/nifty500_acquisition.log"

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def connect():
    return oracledb.connect(
        user=DB['user'], password=DB['password'], dsn=DB['dsn'],
        config_dir=DB['wallet_location'], wallet_location=DB['wallet_location'],
        wallet_password=DB['wallet_password']
    )

def get_count():
    try:
        c = connect().cursor()
        c.execute("SELECT COUNT(*) FROM admin.stock_ohlcv_daily")
        n = c.fetchone()[0]
        c.close()
        return n
    except: return 0

log("="*60)
log("🚀 NIFTY 500 + FNO ACQUISITION (5-YEAR PERIOD)")
log("="*60)

df = pd.read_csv('/workspace/quantmudra/nifty500_symbols.csv')
symbols = list(zip(df['yahoo_symbol'], df['nse_symbol']))
log(f"Loaded {len(symbols)} symbols")

conn = connect()
log(f"Starting DB count: {get_count():,}")

s, f, sk, t = 0, 0, 0, 0
t0 = time.time()

for i, (yh, ns) in enumerate(symbols):
    log(f"[{i+1}/{len(symbols)}] {yh}...")
    
    try:
        d = yf.download(yh, period="5y", interval="1d", auto_adjust=False, progress=False, timeout=15)
        if d.empty:
            log("⚠️ no data")
            sk += 1
            continue
        
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = [c[0] for c in d.columns]
        
        d = d.reset_index()
        d['Date'] = pd.to_datetime(d['Date']).dt.tz_localize(None)
        
        cur = conn.cursor()
        n = 0
        for _, r in d.iterrows():
            cur.execute("""
                MERGE INTO admin.stock_ohlcv_daily t
                USING (SELECT :sym as symbol, :dt as trade_date FROM dual) s
                ON (t.symbol = s.symbol AND t.trade_date = s.trade_date)
                WHEN MATCHED THEN UPDATE SET
                    open_price=:open, high_price=:high, low_price=:low,
                    close_price=:close, adj_close=:adj, volume=:vol,
                    nse_symbol=:nse, updated_at=CURRENT_TIMESTAMP
                WHEN NOT MATCHED THEN INSERT 
                    (symbol,trade_date,open_price,high_price,low_price,close_price,adj_close,volume,nse_symbol)
                VALUES (:sym,:dt,:open,:high,:low,:close,:adj,:vol,:nse)
            """, {
                'sym': yh, 'dt': r['Date'].date(),
                'open': float(r['Open']), 'high': float(r['High']),
                'low': float(r['Low']), 'close': float(r['Close']),
                'adj': float(r['Adj Close']), 'vol': int(r['Volume']), 'nse': ns
            })
            n += 1
        
        conn.commit()
        cur.close()
        log(f"✅ {n:,} records (total: {get_count():,})")
        s += 1; t += n
        
    except Exception as e:
        log(f"❌ {str(e)[:60]}")
        f += 1
    
    time.sleep(0.3)

conn.close()
log("="*60)
log(f"DONE: {s} success, {f} failed, {sk} skipped, {t:,} records")
log(f"Final DB: {get_count():,} records")
log(f"Time: {(time.time()-t0)/60:.1f} min")
log("="*60)
