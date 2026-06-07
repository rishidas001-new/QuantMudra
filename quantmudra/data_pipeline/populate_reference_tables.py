#!/usr/bin/env python3
"""
Populate Reference Tables
STOCK_MASTER, INDEX_CONSTITUENTS, CORPORATE_ACTIONS, STOCK_PRICE_METADATA
"""
import yfinance as yf
import pandas as pd
import oracledb
from datetime import datetime, date, timedelta
import json
import sys

# Database configuration
DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/tmp/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}

# Nifty 50 stocks (as of last rebalancing)
NIFTY50 = [
    'ADANIPORTS.NS', 'ASIANPAINT.NS', 'AXISBANK.NS', 'BAJAJ-AUTO.NS',
    'BAJFINANCE.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS',
    'BRITANNIA.NS', 'CIPLA.NS', 'COALINDIA.NS', 'DIVISLAB.NS',
    'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HCLTECH.NS',
    'HDFCBANK.NS', 'HDFCLIFE.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'HINDUNILVR.NS', 'ICICIBANK.NS', 'INDUSINDBK.NS', 'INFY.NS',
    'ITC.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS', 'LTIM.NS', 'LT.NS',
    'M&M.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'NTPC.NS', 'ONGC.NS',
    'POWERGRID.NS', 'RELIANCE.NS', 'SBILIFE.NS', 'SBIN.NS',
    'SUNPHARMA.NS', 'TATACONSUM.NS', 'TATASTEEL.NS', 'TCS.NS',
    'TECHM.NS', 'TITAN.NS', 'ULTRACEMCO.NS', 'WIPRO.NS'
]

def connect_db():
    return oracledb.connect(
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        dsn=DB_CONFIG['dsn'],
        config_dir=DB_CONFIG['wallet_location'],
        wallet_location=DB_CONFIG['wallet_location'],
        wallet_password=DB_CONFIG['wallet_password']
    )

def populate_stock_master(conn):
    """Populate STOCK_MASTER from OHLCV data"""
    print("\n" + "="*70)
    print("1. POPULATING STOCK_MASTER")
    print("="*70)
    
    cursor = conn.cursor()
    
    # Get all symbols from OHLCV
    cursor.execute("""
        SELECT DISTINCT symbol
        FROM admin.stock_ohlcv_daily
        ORDER BY symbol
    """)
    
    symbols = [row[0] for row in cursor.fetchall()]
    cursor.close()
    
    cursor = conn.cursor()
    rows = 0
    for symbol in symbols:
        try:
            cursor.execute("""
                INSERT INTO admin.stock_master
                (symbol, company_name, is_active, created_at)
                VALUES (:1, :2, 1, CURRENT_TIMESTAMP)
            """, [symbol, symbol.replace('.NS', '')])
            rows += 1
        except Exception as e:
            if 'ORA-00001' not in str(e):
                print(f"  Error inserting {symbol}: {e}")
    
    conn.commit()
    cursor.close()
    print(f"✅ Inserted {rows} stocks into STOCK_MASTER")
    return rows

def populate_index_constituents(conn):
    """Populate INDEX_CONSTITUENTS with Nifty 50/100/500"""
    print("\n" + "="*70)
    print("2. POPULATING INDEX_CONSTITUENTS")
    print("="*70)
    
    cursor = conn.cursor()
    today = date.today()
    
    # Get stocks that exist in OHLCV
    cursor.execute("SELECT symbol FROM admin.stock_ohlcv_daily GROUP BY symbol")
    existing = set([row[0] for row in cursor.fetchall()])
    
    rows = 0
    indices = [
        ('NIFTY50', NIFTY50),
    ]
    
    for index_name, stocks in indices:
        print(f"\n  {index_name}:")
        for symbol in stocks:
            # Check if stock exists
            if symbol not in existing:
                print(f"    ⚠️  {symbol} - not in OHLCV data")
                continue
            
            try:
                cursor.execute("""
                    INSERT INTO admin.index_constituents
                    (index_symbol, stock_symbol, effective_date, is_constituent)
                    VALUES (:1, :2, :3, 1)
                """, [index_name, symbol, today])
                rows += 1
                print(f"    ✅ {symbol}")
            except Exception as e:
                if 'ORA-00001' not in str(e):
                    print(f"    ❌ {symbol}: {str(e)[:30]}")
    
    conn.commit()
    cursor.close()
    print(f"\n✅ Inserted {rows} index constituents")
    return rows

def populate_corporate_actions(conn):
    """Populate CORPORATE_ACTIONS from Yahoo Finance"""
    print("\n" + "="*70)
    print("3. POPULATING CORPORATE_ACTIONS")
    print("="*70)
    
    cursor = conn.cursor()
    
    # Get all symbols
    cursor.execute("SELECT symbol FROM admin.stock_ohlcv_daily GROUP BY symbol ORDER BY symbol")
    symbols = [row[0] for row in cursor.fetchall()]
    
    print(f"Processing {len(symbols)} symbols...")
    
    total_actions = 0
    
    for i, symbol in enumerate(symbols, 1):
        try:
            ticker = yf.Ticker(symbol)
            
            # Get splits (last 5 years)
            splits = ticker.splits
            if splits is not None and not splits.empty:
                cutoff = datetime.now() - timedelta(days=1825)
                for split_date, ratio in splits.items():
                    if split_date >= cutoff:
                        try:
                            cursor.execute("""
                                INSERT INTO admin.corporate_actions
                                (symbol, action_date, action_type, ratio, created_at)
                                VALUES (:1, :2, 'SPLIT', :3, CURRENT_TIMESTAMP)
                            """, [symbol, split_date.date() if hasattr(split_date, 'date') else split_date, float(ratio)])
                            total_actions += 1
                        except Exception as e:
                            if 'ORA-00001' not in str(e):
                                pass
            
            # Get dividends (last 2 years)
            divs = ticker.dividends
            if divs is not None and not divs.empty:
                cutoff = datetime.now() - timedelta(days=730)
                for div_date, amount in divs.items():
                    if div_date >= cutoff:
                        try:
                            cursor.execute("""
                                INSERT INTO admin.corporate_actions
                                (symbol, action_date, action_type, amount, created_at)
                                VALUES (:1, :2, 'DIVIDEND', :3, CURRENT_TIMESTAMP)
                            """, [symbol, div_date.date() if hasattr(div_date, 'date') else div_date, float(amount)])
                            total_actions += 1
                        except Exception as e:
                            if 'ORA-00001' not in str(e):
                                pass
            
            if i % 50 == 0:
                conn.commit()
                print(f"  Processed {i}/{len(symbols)} symbols, {total_actions} actions found...")
                
        except Exception as e:
            print(f"  Error {symbol}: {e}")
    
    conn.commit()
    cursor.close()
    print(f"✅ Found {total_actions} corporate actions")
    return total_actions

def populate_stock_metadata(conn):
    """Populate STOCK_PRICE_METADATA"""
    print("\n" + "="*70)
    print("4. POPULATING STOCK_PRICE_METADATA")
    print("="*70)
    
    cursor = conn.cursor()
    
    # Get stats per stock
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as total_records,
            MIN(trade_date) as min_date,
            MAX(trade_date) as max_date
        FROM admin.stock_ohlcv_daily
        GROUP BY symbol
        ORDER BY symbol
    """)
    
    rows = 0
    for row in cursor:
        symbol = row[0]
        total_records = row[1]
        min_date = row[2]
        max_date = row[3]
        
        # Calculate quality score
        cursor2 = conn.cursor()
        cursor2.execute("""
            SELECT 
                SUM(CASE WHEN close_price > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                SUM(CASE WHEN volume > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
            FROM admin.stock_ohlcv_daily WHERE symbol = :1
        """, [symbol])
        price_score, vol_score = cursor2.fetchone()
        quality_score = (price_score * 0.7 + vol_score * 0.3) if price_score else 0
        cursor2.close()
        
        try:
            cursor.execute("""
                INSERT INTO admin.stock_price_metadata
                (symbol, exchange, series, min_date, max_date, total_records, last_refresh_date, data_quality_score)
                VALUES (:1, 'NSE', 'EQ', :2, :3, :4, CURRENT_TIMESTAMP, :5)
            """, [symbol, min_date, max_date, total_records, quality_score])
            rows += 1
        except Exception as e:
            if 'ORA-00001' not in str(e):
                print(f"  Error {symbol}: {e}")
    
    conn.commit()
    cursor.close()
    print(f"✅ Populated metadata for {rows} stocks")
    return rows

def main():
    print("="*70)
    print("POPULATING REFERENCE TABLES")
    print("="*70)
    
    try:
        conn = connect_db()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)
    
    results = {}
    
    # 1. Stock Master
    results['STOCK_MASTER'] = populate_stock_master(conn)
    
    # 2. Index Constituents
    results['INDEX_CONSTITUENTS'] = populate_index_constituents(conn)
    
    # 3. Corporate Actions (may take a while)
    print("\n⏳ Fetching corporate actions from Yahoo (this may take a while)...")
    results['CORPORATE_ACTIONS'] = populate_corporate_actions(conn)
    
    # 4. Stock Metadata
    results['STOCK_PRICE_METADATA'] = populate_stock_metadata(conn)
    
    conn.close()
    
    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)
    for table, count in results.items():
        print(f"  {table}: {count:,} records")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())