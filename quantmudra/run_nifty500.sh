#!/bin/bash
# Nifty 500 + FNO Bulk Acquisition Script
# Runs in background with logging

LOG_FILE="/home/openhands/.oci/logs/nifty500_acquisition.log"
DB_PASS="QuantMudra@2026"
WALLET_DIR="/home/openhands/.oci/quantmudra_wallet"

echo "============================================================" | tee -a $LOG_FILE
echo "🚀 NIFTY 500 + FNO BULK ACQUISITION" | tee -a $LOG_FILE
echo "Start: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a $LOG_FILE
echo "============================================================" | tee -a $LOG_FILE

python3 << 'PYEOF' 2>&1 | tee -a $LOG_FILE
import yfinance as yf
import pandas as pd
import oracledb
import time
import sys

DB = {
    'user': 'admin', 
    'password': 'QuantMudra@2026', 
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet', 
    'wallet_password': 'QuantMudra@2026'
}

# Load Nifty 500 symbols
symbols_df = pd.read_csv('/workspace/quantmudra/nifty500_symbols.csv')
symbols = list(zip(symbols_df['yahoo_symbol'], symbols_df['nse_symbol']))

print(f"Loaded {len(symbols)} symbols from Nifty 500 list")
print("Using 5-year period")

conn = oracledb.connect(
    user=DB['user'], password=DB['password'], dsn=DB['dsn'],
    config_dir=DB['wallet_location'], wallet_location=DB['wallet_location'],
    wallet_password=DB['wallet_password']
)

success, failed, skipped, total = 0, 0, 0, 0
start_time = time.time()

for i, (yahoo, nse) in enumerate(symbols):
    elapsed_total = time.time() - start_time
    eta = (elapsed_total / max(i, 1)) * (len(symbols) - i - 1) / 60 if i > 0 else 0
    
    print(f"[{i+1}/{len(symbols)}] {yahoo}...", end=" ", flush=True)
    
    try:
        df = yf.download(yahoo, period="5y", interval="1d", auto_adjust=False, 
                        progress=False, timeout=15)
        
        if df.empty:
            print("⚠️ No data")
            skipped += 1
            continue
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        
        df = df.reset_index()
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        
        cursor = conn.cursor()
        stored = 0
        
        for _, row in df.iterrows():
            cursor.execute("""
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
                'sym': yahoo, 'dt': row['Date'].date(),
                'open': float(row['Open']), 'high': float(row['High']),
                'low': float(row['Low']), 'close': float(row['Close']),
                'adj': float(row['Adj Close']), 'vol': int(row['Volume']), 'nse': nse
            })
            stored += 1
        
        conn.commit()
        cursor.close()
        
        print(f"✅ {stored:,} records")
        success += 1
        total += stored
        
    except Exception as e:
        print(f"❌ {str(e)[:40]}")
        failed += 1
    
    time.sleep(0.5)  # Rate limit

conn.close()

end_time = time.time()
duration = (end_time - start_time) / 60

print("\n" + "="*60)
print("ACQUISITION COMPLETE")
print(f"Duration: {duration:.1f} minutes")
print(f"Success: {success}")
print(f"Failed: {failed}")
print(f"Skipped: {skipped}")
print(f"Total Records: {total:,}")

# Final count
conn = oracledb.connect(
    user=DB['user'], password=DB['password'], dsn=DB['dsn'],
    config_dir=DB['wallet_location'], wallet_location=DB['wallet_location'],
    wallet_password=DB['wallet_password']
)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM admin.stock_ohlcv_daily")
print(f"Database Total: {cursor.fetchone()[0]:,} records")
cursor.execute("SELECT COUNT(DISTINCT symbol) FROM admin.stock_ohlcv_daily")
print(f"Unique Stocks: {cursor.fetchone()[0]}")
cursor.close()
conn.close()

PYEOF

echo "End: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a $LOG_FILE
