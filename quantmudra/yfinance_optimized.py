"""
QuantMudra - Optimized Yahoo Finance to Oracle ATP
Uses batch inserts for faster processing
"""

import yfinance as yf
import pandas as pd
import oracledb
import time
from datetime import datetime

# Database config
DB = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}

def connect():
    return oracledb.connect(
        user=DB['user'], password=DB['password'], dsn=DB['dsn'],
        config_dir=DB['wallet_location'], wallet_location=DB['wallet_location'],
        wallet_password=DB['wallet_password']
    )

def store_batch(conn, symbol, nse_sym, df):
    """Store using executemany for speed"""
    cursor = conn.cursor()
    
    rows = []
    for _, row in df.iterrows():
        rows.append((
            symbol, row['Date'].date(),
            float(row['Open']), float(row['High']), float(row['Low']),
            float(row['Close']), float(row['Adj Close']), int(row['Volume']), nse_sym
        ))
    
    cursor.executemany("""
        MERGE INTO admin.stock_ohlcv_daily t
        USING (SELECT :1 as symbol, :2 as trade_date FROM dual) s
        ON (t.symbol = s.symbol AND t.trade_date = s.trade_date)
        WHEN MATCHED THEN UPDATE SET
            open_price = :3, high_price = :4, low_price = :5,
            close_price = :6, adj_close = :7, volume = :8,
            nse_symbol = :9, updated_at = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN INSERT 
            (symbol, trade_date, open_price, high_price, low_price, 
             close_price, adj_close, volume, nse_symbol)
        VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9)
    """, rows)
    
    conn.commit()
    cursor.close()
    return len(rows)

def fetch_and_store(symbols):
    print("="*60)
    print("🚀 OPTIMIZED BULK ACQUISITION")
    print("="*60)
    
    conn = connect()
    success, failed, total = 0, 0, 0
    
    for i, (yahoo, nse) in enumerate(symbols):
        print(f"\n[{i+1}/{len(symbols)}] {yahoo}...", end=" ", flush=True)
        start = time.time()
        
        try:
            df = yf.download(yahoo, period="10y", interval="1d", auto_adjust=False, 
                           progress=False, timeout=15)
            
            if df.empty:
                print("⚠️ No data")
                failed += 1
                continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            
            stored = store_batch(conn, yahoo, nse, df)
            elapsed = time.time() - start
            print(f"✅ {stored:,} records ({elapsed:.1f}s)")
            success += 1
            total += stored
            
        except Exception as e:
            print(f"❌ {str(e)[:30]}")
            failed += 1
        
        time.sleep(0.5)  # Rate limit
    
    conn.close()
    
    print("\n" + "="*60)
    print(f"Done: {success} success, {failed} failed, {total:,} records")
    
    # Final count
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admin.stock_ohlcv_daily")
    print(f"Total in DB: {cursor.fetchone()[0]:,} records")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import sys
    # Nifty 50 list (can be passed as argument)
    symbols = [
        ("ADANIPORTS.NS", "NSE:ADANIPORTS-EQ"),
        ("ASIANPAINT.NS", "NSE:ASIANPAINT-EQ"),
        ("AXISBANK.NS", "NSE:AXISBANK-EQ"),
        ("BAJAJ-AUTO.NS", "NSE:BAJAJ-AUTO-EQ"),
        ("BAJFINANCE.NS", "NSE:BAJFINANCE-EQ"),
        ("BAJAJFINSV.NS", "NSE:BAJAJFINSV-EQ"),
        ("BHARTIARTL.NS", "NSE:BHARTIARTL-EQ"),
        ("BPCL.NS", "NSE:BPCL-EQ"),
        ("BRITANNIA.NS", "NSE:BRITANNIA-EQ"),
        ("CIPLA.NS", "NSE:CIPLA-EQ"),
        ("COALINDIA.NS", "NSE:COALINDIA-EQ"),
        ("DIVISLAB.NS", "NSE:DIVISLAB-EQ"),
        ("DRREDDY.NS", "NSE:DRREDDY-EQ"),
        ("EICHERMOT.NS", "NSE:EICHERMOT-EQ"),
        ("GRASIM.NS", "NSE:GRASIM-EQ"),
        ("HCLTECH.NS", "NSE:HCLTECH-EQ"),
        ("HDFCBANK.NS", "NSE:HDFCBANK-EQ"),
        ("HDFCLIFE.NS", "NSE:HDFCLIFE-EQ"),
        ("HEROMOTOCO.NS", "NSE:HEROMOTOCO-EQ"),
        ("HINDALCO.NS", "NSE:HINDALCO-EQ"),
    ]
    fetch_and_store(symbols)
