#!/usr/bin/env python3
"""
Backfill Script - Fetch 2016-2020 data for all stocks
Uses date range instead of period to get full history
"""
import yfinance as yf
import pandas as pd
import oracledb
import time
import os

DB = {
    'user': 'admin', 
    'password': 'QuantMudra@2026', 
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet', 
    'wallet_password': 'QuantMudra@2026'
}

LOG_DIR = '/home/openhands/.oci/logs'
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = f"{LOG_DIR}/backfill_2016.log"

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

def get_symbols_needing_backfill():
    """Get symbols that don't have 2016 data"""
    conn = connect()
    cursor = conn.cursor()
    
    # Get all symbols and their min date
    cursor.execute("""
        SELECT symbol, MIN(trade_date) as min_date
        FROM admin.stock_ohlcv_daily
        GROUP BY symbol
        HAVING MIN(trade_date) > DATE '2016-01-01'
    """)
    
    symbols = []
    for row in cursor:
        symbols.append({'symbol': row[0], 'start_date': row[1]})
    
    cursor.close()
    conn.close()
    return symbols

def get_nse_symbol(symbol):
    """Get NSE symbol from master table"""
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nse_symbol FROM (
                SELECT yahoo_symbol, nse_symbol FROM admin.stock_master
                UNION
                SELECT yahoo_symbol, nse_symbol FROM (
                    SELECT yahoo_symbol, nse_symbol FROM (
                        SELECT DISTINCT symbol as yahoo_symbol, nse_symbol 
                        FROM admin.stock_ohlcv_daily
                    )
                )
            ) WHERE yahoo_symbol = :1
        """, [symbol])
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else f"NSE:{symbol.replace('.NS','')}-EQ"
    except:
        return f"NSE:{symbol.replace('.NS','')}-EQ"

def store_data(symbol, nse_symbol, df):
    """Store OHLCV data using MERGE"""
    if df.empty:
        return 0
    
    conn = connect()
    cursor = conn.cursor()
    stored = 0
    
    rows = []
    for _, row in df.iterrows():
        rows.append({
            'sym': symbol,
            'dt': row['Date'].date(),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'adj': float(row['Adj Close']),
            'vol': int(row['Volume']),
            'nse': nse_symbol
        })
    
    cursor.executemany("""
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
    """, rows)
    
    conn.commit()
    cursor.close()
    conn.close()
    return len(rows)

def main():
    log("="*60)
    log("🚀 BACKFILL 2016-2020 DATA")
    log("="*60)
    
    # Get symbols needing backfill
    symbols = get_symbols_needing_backfill()
    log(f"Found {len(symbols)} stocks needing backfill")
    
    # Get initial count
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admin.stock_ohlcv_daily")
    start_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    log(f"Starting DB count: {start_count:,}")
    
    t0 = time.time()
    success, failed, total = 0, 0, 0
    
    for i, item in enumerate(symbols):
        sym = item['symbol']
        current_start = item['start_date']
        
        log(f"[{i+1}/{len(symbols)}] {sym} (currently starts: {current_start.strftime('%Y-%m-%d')})...")
        
        try:
            # Download data from 2016-01-01 to current start - 1 day
            # This fills the gap before existing data
            if current_start.year > 2016:
                end_date = current_start.strftime('%Y-%m-%d')
                start_date = '2016-01-01'
                
                df = yf.download(sym, start=start_date, end=end_date, 
                               interval="1d", auto_adjust=False, progress=False, timeout=30)
                
                if df.empty:
                    log(f"   ⚠️ No data for {start_date} to {end_date}")
                    failed += 1
                    continue
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [col[0] for col in df.columns]
                
                df = df.reset_index()
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
                
                # Filter to only dates before current start
                df = df[df['Date'] < pd.Timestamp(current_start)]
                
                if df.empty:
                    log(f"   ⚠️ No gap data to fill")
                    continue
                
                nse_sym = get_nse_symbol(sym)
                stored = store_data(sym, nse_sym, df)
                
                log(f"   ✅ Added {stored:,} records (filling {start_date} to {end_date})")
                success += 1
                total += stored
            else:
                log(f"   ✓ Already has 2016 data")
                
        except Exception as e:
            log(f"   ❌ {str(e)[:50]}")
            failed += 1
        
        time.sleep(0.3)
    
    # Final count
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admin.stock_ohlcv_daily")
    final_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    duration = (time.time() - t0) / 60
    
    log("="*60)
    log("✅ BACKFILL COMPLETE")
    log(f"Duration: {duration:.1f} minutes")
    log(f"Success: {success}, Failed: {failed}")
    log(f"New Records: {final_count - start_count:,}")
    log(f"Final DB Count: {final_count:,}")
    log("="*60)

if __name__ == "__main__":
    main()
