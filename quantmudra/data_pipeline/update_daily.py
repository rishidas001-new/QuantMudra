#!/usr/bin/env python3
"""
Daily OHLCV Data Update Script
Fetches yesterday's closing data for all 500 stocks
Runs daily at 6:30 PM IST (1:00 PM UTC)

Logs execution to JOB_EXECUTION_LOG table for monitoring
"""
import yfinance as yf
import pandas as pd
import oracledb
from datetime import datetime, date, timedelta
import time
import sys
import logging
import traceback

# Add parent directory to path for imports
sys.path.insert(0, '/workspace/quantmudra')
from scripts.job_logger import JobLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/workspace/quantmudra/logs/update_daily.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/tmp/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}

def connect_db():
    """Create database connection"""
    return oracledb.connect(
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        dsn=DB_CONFIG['dsn'],
        config_dir=DB_CONFIG['wallet_location'],
        wallet_location=DB_CONFIG['wallet_location'],
        wallet_password=DB_CONFIG['wallet_password']
    )

def get_all_symbols(conn):
    """Get list of all stock symbols from database"""
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM admin.stock_master ORDER BY symbol")
    symbols = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return symbols

def get_last_update_date(conn):
    """Get the most recent trading date in the database"""
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(trade_date) FROM admin.stock_ohlcv_daily")
    result = cursor.fetchone()[0]
    cursor.close()
    return result

def update_stock_data(conn, symbol, start_date, end_date):
    """Download and update data for a single stock"""
    try:
        df = yf.download(symbol, start=start_date, end=end_date,
                       interval="1d", auto_adjust=False, progress=False, timeout=30)
        
        if df.empty:
            return {'symbol': symbol, 'status': 'NO_DATA', 'records': 0}
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        
        df = df.reset_index()
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        
        cursor = conn.cursor()
        rows_inserted = 0
        
        for _, row in df.iterrows():
            dt = row['Date'].date()
            nse_sym = f"NSE:{symbol.replace('.NS','')}-EQ"
            
            cursor.execute("""
                MERGE INTO admin.stock_ohlcv_daily t
                USING (SELECT :sym as symbol, :dt as trade_date FROM dual) s
                ON (t.symbol = s.symbol AND t.trade_date = s.trade_date)
                WHEN MATCHED THEN UPDATE SET
                    open_price = :open, high_price = :high, low_price = :low,
                    close_price = :close, adj_close = :adj, volume = :vol,
                    nse_symbol = :nse, updated_at = CURRENT_TIMESTAMP
                WHEN NOT MATCHED THEN INSERT
                    (symbol, trade_date, open_price, high_price, low_price, 
                     close_price, adj_close, volume, nse_symbol)
                VALUES (:sym, :dt, :open, :high, :low, :close, :adj, :vol, :nse)
            """, {
                'sym': symbol, 'dt': dt,
                'open': float(row['Open']), 'high': float(row['High']),
                'low': float(row['Low']), 'close': float(row['Close']),
                'adj': float(row['Adj Close']), 'vol': int(row['Volume']),
                'nse': nse_sym
            })
            rows_inserted += 1
        
        conn.commit()
        cursor.close()
        
        return {'symbol': symbol, 'status': 'SUCCESS', 'records': rows_inserted}
        
    except Exception as e:
        return {'symbol': symbol, 'status': 'ERROR', 'error': str(e), 'records': 0}

def log_update(conn, run_date, total_stocks, success_count, failed_count, 
               records_updated, status):
    """Log the update run to DATA_REFRESH_LOG table"""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO admin.data_refresh_log 
        (refresh_date, total_stocks, success_count, failed_count, 
         records_updated, status, created_at)
        VALUES (:1, :2, :3, :4, :5, :6, CURRENT_TIMESTAMP)
    """, [run_date, total_stocks, success_count, failed_count, 
          records_updated, status])
    conn.commit()
    cursor.close()

def is_trading_day(check_date):
    """Check if a date is a valid trading day"""
    if check_date.weekday() >= 5:
        return False
    year = check_date.year
    holidays = [
        date(year, 1, 1), date(year, 1, 26), date(year, 8, 15),
        date(year, 10, 2), date(year, 12, 25),
    ]
    return check_date not in holidays

def get_previous_trading_day(from_date, lookback_days=10):
    """Get the most recent valid trading day"""
    for i in range(1, lookback_days + 1):
        check = from_date - timedelta(days=i)
        if is_trading_day(check):
            return check
    return from_date - timedelta(days=1)

def main():
    start_time = datetime.now()
    job_logger = JobLogger(DB_CONFIG)
    job_logger.connect()
    log_id = job_logger.start_job('update_daily')
    
    logger.info("="*70)
    logger.info("DAILY DATA UPDATE - STARTED")
    logger.info("="*70)
    
    today = date.today()
    
    if today.weekday() == 0:
        target_date = today - timedelta(days=3)
    elif today.weekday() >= 5:
        target_date = get_previous_trading_day(today)
    else:
        target_date = today - timedelta(days=1)
    
    logger.info(f"Target date: {target_date}")
    
    try:
        conn = connect_db()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        job_logger.log_failure(e)
        job_logger.close()
        sys.exit(1)
    
    last_update = get_last_update_date(conn)
    logger.info(f"Last update in DB: {last_update}")
    
    if last_update and last_update.date() >= target_date:
        logger.info(f"Data already updated for {target_date}. Skipping.")
        conn.close()
        job_logger.log_success(0, 0)
        job_logger.close()
        sys.exit(0)
    
    symbols = get_all_symbols(conn)
    logger.info(f"Total symbols to update: {len(symbols)}")
    
    success_count = 0
    failed_count = 0
    total_records = 0
    new_records = 0
    updated_records = 0
    
    start_date = (last_update.date() + timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    logger.info(f"Fetching data from {start_date} to {end_date}")
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] {symbol}...", end=" ")
        
        result = update_stock_data(conn, symbol, start_date, end_date)
        
        if result['status'] == 'SUCCESS':
            logger.info(f"OK +{result['records']}")
            success_count += 1
            total_records += result['records']
            new_records += result['records']  # Simplified - actual tracking needs DB check
        elif result['status'] == 'NO_DATA':
            logger.info("SKIP")
        else:
            logger.info(f"ERR")
            failed_count += 1
        
        time.sleep(0.1)
    
    status = 'COMPLETED' if failed_count == 0 else 'COMPLETED_WITH_ERRORS'
    log_update(conn, target_date, len(symbols), success_count, 
               failed_count, total_records, status)
    
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info("="*70)
    logger.info("DAILY DATA UPDATE - COMPLETED")
    logger.info("="*70)
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info(f"Success: {success_count}, Failed: {failed_count}")
    logger.info(f"Total records: {total_records}")
    
    conn.close()
    
    # Log to JOB_EXECUTION_LOG table
    if failed_count == 0:
        job_logger.log_success(records_added=new_records, records_updated=total_records - new_records)
    elif success_count > 0:
        job_logger.log_partial(records_added=new_records, records_updated=total_records - new_records, 
                               records_failed=failed_count)
    else:
        job_logger.log_failure(Exception(f"All {failed_count} stocks failed"))
    
    job_logger.close()
    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())