#!/usr/bin/env python3
"""
Index Composition Update Script
Tracks Nifty 50/100/500/Next 50 changes
Adds new listings (IPOs) and removes delisted stocks
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
        logging.FileHandler('/workspace/quantmudra/logs/index_composition.log'),
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

# Index ETF symbols for tracking
INDEX_SYMBOLS = {
    'NIFTY50': '^NSEI',
    'NIFTY100': '^NSEMD100', 
    'NIFTY200': '^CNX200',
    'NIFTY500': '^CRSLDX',
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

def get_current_symbols(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM admin.stock_master")
    symbols = set([row[0] for row in cursor.fetchall()])
    cursor.close()
    return symbols

def get_symbols_by_index(conn, index_name):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT stock_symbol FROM admin.index_constituents
        WHERE index_symbol = :1 AND is_constituent = 1
    """, [index_name])
    symbols = set([row[0] for row in cursor.fetchall()])
    cursor.close()
    return symbols

def fetch_index_components(index_symbol):
    """Fetch index components from Yahoo Finance"""
    try:
        ticker = yf.Ticker(index_symbol)
        holdings = ticker.info.get('component_tracking_index', [])
        
        if not holdings:
            # Try alternative approach
            logger.warning(f"Could not fetch components for {index_symbol}")
            return []
        
        return holdings
    except Exception as e:
        logger.error(f"Error fetching {index_symbol}: {e}")
        return []

def fetch_nifty50_components():
    """Fetch Nifty 50 components from NSE website or API"""
    try:
        # Try Yahoo Finance first
        ticker = yf.Ticker("^NSEI")
        constituents = ticker.constituents or []
        
        if not constituents:
            # Fallback: use known list (quarterly rebalancing)
            logger.info("Using fallback Nifty 50 list")
            constituents = get_fallback_nifty50()
        
        return constituents
    except Exception as e:
        logger.error(f"Error: {e}")
        return get_fallback_nifty50()

def get_fallback_nifty50():
    """Fallback Nifty 50 list (as of last rebalancing)"""
    return [
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

def fetch_recent_ipos(conn, lookback_days=90):
    """Find recently listed stocks (potential IPOs)"""
    cursor = conn.cursor()
    cutoff_date = date.today()
    from datetime import timedelta
    cutoff_date = cutoff_date - timedelta(days=lookback_days)
    
    cursor.execute("""
        SELECT symbol, MIN(trade_date) as listing_date
        FROM admin.stock_ohlcv_daily
        WHERE MIN(trade_date) >= :1
        GROUP BY symbol
        ORDER BY listing_date DESC
    """, [cutoff_date])
    
    recent = []
    for row in cursor:
        symbol = row[0]
        listing_date = row[1]
        
        # Check if not already in stock_master
        cursor2 = conn.cursor()
        cursor2.execute("SELECT 1 FROM admin.stock_master WHERE symbol = :1", [symbol])
        exists = cursor2.fetchone() is not None
        cursor2.close()
        
        if not exists:
            recent.append({'symbol': symbol, 'listing_date': listing_date})
    
    cursor.close()
    return recent

def update_index_composition(conn, index_name, symbols, effective_date):
    """Update index composition in database"""
    cursor = conn.cursor()
    
    for symbol in symbols:
        try:
            cursor.execute("""
                INSERT INTO admin.index_constituents
                (index_symbol, stock_symbol, effective_date, is_constituent)
                VALUES (:1, :2, :3, 1)
            """, [index_name, symbol, effective_date])
        except Exception as e:
            if 'ORA-00001' not in str(e):
                logger.error(f"Error adding {symbol} to {index_name}: {e}")
    
    conn.commit()
    cursor.close()

def mark_removed_stocks(conn, index_name, old_symbols, new_symbols, effective_date):
    """Mark stocks that were removed from the index"""
    removed = old_symbols - new_symbols
    
    if removed:
        cursor = conn.cursor()
        for symbol in removed:
            try:
                cursor.execute("""
                    UPDATE admin.index_constituents
                    SET end_date = :1, is_constituent = 0
                    WHERE index_symbol = :2 AND stock_symbol = :3 AND end_date IS NULL
                """, [effective_date, index_name, symbol])
                logger.info(f"  Removed from {index_name}: {symbol}")
            except Exception as e:
                logger.error(f"Error removing {symbol}: {e}")
        
        conn.commit()
        cursor.close()
    
    return removed

def add_new_stock_master(conn, symbol, listing_date=None):
    """Add new stock to stock_master table"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO admin.stock_master
            (symbol, company_name, is_active, created_at)
            VALUES (:1, :2, 1, CURRENT_TIMESTAMP)
        """, [symbol, symbol.replace('.NS', '')])
        conn.commit()
        logger.info(f"  Added new stock: {symbol}")
    except Exception as e:
        if 'ORA-00001' not in str(e):
            logger.error(f"  Error adding {symbol}: {e}")
    
    cursor.close()

def main():
    logger.info("="*70)
    logger.info("INDEX COMPOSITION UPDATE - STARTED")
    logger.info("="*70)
    
    try:
        conn = connect_db()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
    
    effective_date = date.today()
    total_changes = 0
    
    # Process Nifty 50
    logger.info("Processing Nifty 50...")
    current_symbols = get_symbols_by_index(conn, 'NIFTY50')
    new_symbols = set([s + '.NS' for s in get_fallback_nifty50()])
    
    added = new_symbols - current_symbols
    removed = mark_removed_stocks(conn, 'NIFTY50', current_symbols, new_symbols, effective_date)
    
    if added:
        update_index_composition(conn, 'NIFTY50', added, effective_date)
        logger.info(f"  Added {len(added)} new stocks")
        total_changes += len(added)
    
    if removed:
        total_changes += len(removed)
    
    # Check for recent IPOs
    logger.info("Checking for recent IPOs...")
    recent_ipos = fetch_recent_ipos(conn, 90)
    if recent_ipos:
        logger.info(f"Found {len(recent_ipos)} recent listings:")
        for ipo in recent_ipos:
            logger.info(f"  {ipo['symbol']}: {ipo['listing_date']}")
            add_new_stock_master(conn, ipo['symbol'], ipo['listing_date'])
            total_changes += 1
    
    # Update stock_master with any new symbols from OHLCV
    logger.info("Syncing stock_master with OHLCV data...")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO admin.stock_master (symbol, nse_symbol, is_active, created_at)
        SELECT DISTINCT symbol, 'NSE:' || REPLACE(symbol, '.NS', '') || '-EQ', 'Y', CURRENT_TIMESTAMP
        FROM admin.stock_ohlcv_daily o
        WHERE NOT EXISTS (
            SELECT 1 FROM admin.stock_master m WHERE m.symbol = o.symbol
        )
    """)
    new_stocks = cursor.rowcount
    conn.commit()
    cursor.close()
    
    if new_stocks > 0:
        logger.info(f"Added {new_stocks} new stocks to stock_master")
        total_changes += new_stocks
    
    conn.close()
    
    logger.info("="*70)
    logger.info("INDEX COMPOSITION UPDATE - COMPLETED")
    logger.info("="*70)
    logger.info(f"Total changes: {total_changes}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())