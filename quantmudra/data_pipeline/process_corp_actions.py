#!/usr/bin/env python3
"""
Corporate Actions Processor
Handles stock splits, bonuses, dividends, and rights issues
Adjusts historical prices accordingly
"""
import yfinance as yf
import pandas as pd
import oracledb
from datetime import datetime, date
import sys
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/workspace/quantmudra/logs/corp_actions.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}

def connect_db():
    return oracledb.connect(
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        dsn=DB_CONFIG['dsn'],
        config_dir=DB_CONFIG['wallet_location'],
        wallet_location=DB_CONFIG['wallet_location'],
        wallet_password=DB_CONFIG['wallet_password']
    )

def get_all_symbols(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM admin.stock_master ORDER BY symbol")
    symbols = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return symbols

def get_last_corp_action_date(conn, symbol):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(action_date) FROM admin.corporate_actions
        WHERE symbol = :1
    """, [symbol])
    result = cursor.fetchone()[0]
    cursor.close()
    return result

def fetch_stock_splits(symbol, start_date):
    """Fetch stock split information from Yahoo"""
    try:
        ticker = yf.Ticker(symbol)
        splits = ticker.splits
        if splits is None or splits.empty:
            return []
        
        splits = splits.reset_index()
        splits.columns = ['date', 'split_ratio']
        splits = splits[splits['date'] >= pd.Timestamp(start_date)]
        return splits.to_dict('records')
    except Exception as e:
        logger.warning(f"Could not fetch splits for {symbol}: {e}")
        return []

def fetch_dividends(symbol, start_date):
    """Fetch dividend information from Yahoo"""
    try:
        ticker = yf.Ticker(symbol)
        divs = ticker.dividends
        if divs is None or divs.empty:
            return []
        
        divs = divs.reset_index()
        divs.columns = ['date', 'dividend']
        divs = divs[divs['date'] >= pd.Timestamp(start_date)]
        return divs.to_dict('records')
    except Exception as e:
        logger.warning(f"Could not fetch dividends for {symbol}: {e}")
        return []

def log_corporate_action(conn, symbol, action_type, action_date, details, status):
    """Log corporate action to database"""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO admin.corporate_actions
        (symbol, action_date, action_type, ratio, amount, created_at)
        VALUES (:1, :2, :3, :4, :5, CURRENT_TIMESTAMP)
    """, [symbol, action_date, action_type, 
          details.get('ratio'), details.get('amount')])
    conn.commit()
    cursor.close()

def apply_stock_split(conn, symbol, split_date, split_ratio):
    """Apply stock split to historical data (before split date)"""
    cursor = conn.cursor()
    
    # Parse split ratio (e.g., "2:1" means 2 old shares = 1 new share)
    if ':' in str(split_ratio):
        old, new = map(float, str(split_ratio).split(':'))
        factor = old / new
    else:
        factor = float(split_ratio)
    
    logger.info(f"  Applying split {split_ratio} to {symbol} data before {split_date}")
    
    # Update prices for dates before split
    cursor.execute("""
        UPDATE admin.stock_ohlcv_daily
        SET open_price = open_price / :1,
            high_price = high_price / :1,
            low_price = low_price / :1,
            close_price = close_price / :1,
            adj_close = adj_close / :1,
            updated_at = CURRENT_TIMESTAMP
        WHERE symbol = :2 AND trade_date < :3
    """, [factor, symbol, split_date])
    
    rows_updated = cursor.rowcount
    conn.commit()
    cursor.close()
    
    return rows_updated

def apply_dividend_adjustment(conn, symbol, div_date, dividend):
    """Track dividend for ex-date adjustment"""
    cursor = conn.cursor()
    
    logger.info(f"  Dividend ${dividend} for {symbol} on {div_date}")
    
    # Update adj_close to reflect dividend adjustment
    cursor.execute("""
        UPDATE admin.stock_ohlcv_daily
        SET adj_close = close_price,
            updated_at = CURRENT_TIMESTAMP
        WHERE symbol = :1 AND trade_date >= :2
    """, [symbol, div_date])
    
    rows_updated = cursor.rowcount
    conn.commit()
    cursor.close()
    
    return rows_updated

def process_symbol(conn, symbol):
    """Process corporate actions for a single symbol"""
    # Get last processed date (default to 7 days ago for daily runs)
    last_date = get_last_corp_action_date(conn, symbol)
    if last_date:
        from datetime import timedelta
        start_date = (last_date - timedelta(days=7)).strftime('%Y-%m-%d')
    else:
        # Only check last 30 days if never processed
        from datetime import timedelta
        start_date = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    actions_found = 0
    
    # Fetch and process splits
    splits = fetch_stock_splits(symbol, start_date)
    for split in splits:
        split_date = pd.Timestamp(split['date']).tz_localize(None).date()
        ratio = split['split_ratio']
        
        logger.info(f"  Found split: {ratio} on {split_date}")
        
        try:
            rows = apply_stock_split(conn, symbol, split_date, ratio)
            log_corporate_action(conn, symbol, 'SPLIT', split_date, 
                               {'ratio': ratio}, 'APPLIED')
            actions_found += 1
            logger.info(f"    Updated {rows} records")
        except Exception as e:
            logger.error(f"    Error applying split: {e}")
            log_corporate_action(conn, symbol, 'SPLIT', split_date, 
                               {'ratio': ratio, 'error': str(e)}, 'ERROR')
    
    # Fetch and process dividends
    dividends = fetch_dividends(symbol, start_date)
    for div in dividends:
        div_date = pd.Timestamp(div['date']).tz_localize(None).date()
        amount = div['dividend']
        
        if amount > 0:
            logger.info(f"  Found dividend: ${amount} on {div_date}")
            
            try:
                rows = apply_dividend_adjustment(conn, symbol, div_date, amount)
                log_corporate_action(conn, symbol, 'DIVIDEND', div_date, 
                                   {'amount': amount}, 'APPLIED')
                actions_found += 1
                logger.info(f"    Updated {rows} records")
            except Exception as e:
                logger.error(f"    Error applying dividend: {e}")
                log_corporate_action(conn, symbol, 'DIVIDEND', div_date, 
                                   {'amount': amount, 'error': str(e)}, 'ERROR')
    
    return actions_found

def main():
    logger.info("="*70)
    logger.info("CORPORATE ACTIONS PROCESSOR - STARTED")
    logger.info("="*70)
    
    try:
        conn = connect_db()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
    
    symbols = get_all_symbols(conn)
    logger.info(f"Processing {len(symbols)} symbols")
    
    total_actions = 0
    for i, symbol in enumerate(symbols, 1):
        try:
            actions = process_symbol(conn, symbol)
            if actions > 0:
                logger.info(f"[{i}/{len(symbols)}] {symbol}: {actions} actions")
            total_actions += actions
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
    
    conn.close()
    
    logger.info("="*70)
    logger.info("CORPORATE ACTIONS PROCESSOR - COMPLETED")
    logger.info("="*70)
    logger.info(f"Total actions processed: {total_actions}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())