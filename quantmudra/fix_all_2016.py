#!/usr/bin/env python3
"""
Comprehensive 2016 data fix for all remaining stocks
"""
import yfinance as yf
import pandas as pd
import oracledb
import time

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

def main():
    print("="*70)
    print("FIXING ALL REMAINING 2016 DATA GAPS")
    print("="*70)
    
    conn = connect()
    cursor = conn.cursor()
    
    # Get all stocks that don't have 2016 data
    cursor.execute("""
        SELECT symbol, MIN(trade_date) as start_date
        FROM admin.stock_ohlcv_daily
        GROUP BY symbol
        HAVING MIN(trade_date) > DATE '2016-01-01'
        ORDER BY MIN(trade_date) ASC
    """)
    
    stocks = []
    for row in cursor:
        stocks.append({'symbol': row[0], 'start_date': row[1]})
    
    print(f"Found {len(stocks)} stocks needing 2016 data")
    
    cursor.execute("SELECT COUNT(*) FROM admin.stock_ohlcv_daily")
    start_total = cursor.fetchone()[0]
    print(f"Starting records: {start_total:,}")
    
    cursor.close()
    conn.close()
    
    success, failed, total_added = 0, 0, 0
    t0 = time.time()
    
    for i, item in enumerate(stocks):
        sym = item['symbol']
        current_start = item['start_date']
        
        # Skip stocks that IPO'd after 2016
        if current_start.year > 2016:
            print(f"[{i+1}/{len(stocks)}] {sym} ({current_start.strftime('%Y-%m-%d')})...", end=" ")
            
            try:
                end_date = current_start.strftime('%Y-%m-%d')
                
                df = yf.download(sym, start='2016-01-01', end=end_date,
                               interval="1d", auto_adjust=False, progress=False, timeout=30)
                
                if df.empty:
                    print("⚠️ No data")
                    failed += 1
                    continue
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [col[0] for col in df.columns]
                
                df = df.reset_index()
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
                
                # Filter to dates before current start
                df = df[df['Date'] < pd.Timestamp(current_start)]
                
                if df.empty:
                    print("✓ No gap")
                    continue
                
                # Store
                conn = connect()
                cursor = conn.cursor()
                
                rows = []
                for _, row in df.iterrows():
                    rows.append({
                        'sym': sym,
                        'dt': row['Date'].date(),
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close']),
                        'adj': float(row['Adj Close']),
                        'vol': int(row['Volume']),
                        'nse': f"NSE:{sym.replace('.NS','')}-EQ"
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
                
                print(f"✅ +{len(rows)}")
                success += 1
                total_added += len(rows)
                
            except Exception as e:
                print(f"❌ {str(e)[:30]}")
                failed += 1
        
        time.sleep(0.3)
    
    # Final stats
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admin.stock_ohlcv_daily")
    final_total = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    duration = (time.time() - t0) / 60
    
    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)
    print(f"Duration: {duration:.1f} minutes")
    print(f"Success: {success}, Failed: {failed}")
    print(f"Added: {total_added:,} records")
    print(f"Final: {start_total:,} → {final_total:,}")

if __name__ == "__main__":
    main()
