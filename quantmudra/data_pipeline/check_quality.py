#!/usr/bin/env python3
"""
Data Quality Validation Script
Checks for anomalies: zero prices, missing days, price gaps >20%
Flags issues in DATA_QUALITY_LOG table
"""
import oracledb
from datetime import datetime, date, timedelta
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/workspace/quantmudra/logs/check_quality.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/tmp/quantmudra_wallet',
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

def check_zero_prices(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, trade_date, open_price, high_price, low_price, close_price
        FROM admin.stock_ohlcv_daily
        WHERE open_price = 0 OR high_price = 0 OR low_price = 0 OR close_price = 0
           OR open_price IS NULL OR high_price IS NULL OR low_price IS NULL OR close_price IS NULL
        ORDER BY trade_date DESC
    """)
    issues = cursor.fetchall()
    cursor.close()
    return issues

def check_missing_trading_days(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, MIN(trade_date), MAX(trade_date)
        FROM admin.stock_ohlcv_daily
        GROUP BY symbol
        HAVING MIN(trade_date) <= DATE '2019-01-01'
    """)
    
    stocks = cursor.fetchall()
    issues = []
    
    for symbol, min_date, max_date in stocks:
        cursor.execute("""
            SELECT trade_date FROM admin.stock_ohlcv_daily
            WHERE symbol = :1 AND trade_date >= :2 AND trade_date <= :3
            ORDER BY trade_date
        """, [symbol, min_date, max_date])
        
        dates = [row[0] for row in cursor.fetchall()]
        
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i-1]).days
            if gap > 5:
                issues.append({
                    'symbol': symbol,
                    'date1': dates[i-1],
                    'date2': dates[i],
                    'gap_days': gap
                })
    
    cursor.close()
    return issues

def check_price_gaps(conn, threshold=20):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            a.symbol, a.trade_date, a.close_price, b.close_price,
            ROUND((b.close_price - a.close_price) * 100.0 / a.close_price, 2) as change_pct
        FROM admin.stock_ohlcv_daily a
        JOIN admin.stock_ohlcv_daily b ON a.symbol = b.symbol AND b.trade_date = a.trade_date + 1
        WHERE a.close_price > 0 AND b.close_price > 0
          AND ABS((b.close_price - a.close_price) * 100.0 / a.close_price) > :1
        ORDER BY ABS((b.close_price - a.close_price) * 100.0 / a.close_price) DESC
    """, [threshold])
    
    issues = cursor.fetchall()
    cursor.close()
    return issues

def check_volume_anomalies(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, trade_date, volume
        FROM admin.stock_ohlcv_daily
        WHERE volume = 0 OR volume IS NULL
        ORDER BY trade_date DESC
    """)
    issues = cursor.fetchall()
    cursor.close()
    return issues

def check_duplicate_dates(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, trade_date, COUNT(*) as cnt
        FROM admin.stock_ohlcv_daily
        GROUP BY symbol, trade_date
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """)
    issues = cursor.fetchall()
    cursor.close()
    return issues

def log_quality_issue(conn, issue_type, symbol, details, severity):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO admin.data_quality_log 
        (check_date, issue_type, symbol, details, severity, created_at)
        VALUES (CURRENT_DATE, :1, :2, :3, :4, CURRENT_TIMESTAMP)
    """, [issue_type, symbol, details, severity])
    conn.commit()
    cursor.close()

def generate_quality_score(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as total_days,
            SUM(CASE WHEN close_price > 0 THEN 1 ELSE 0 END) as valid_days,
            SUM(CASE WHEN volume > 0 THEN 1 ELSE 0 END) as volume_valid
        FROM admin.stock_ohlcv_daily
        GROUP BY symbol
        ORDER BY symbol
    """)
    
    scores = []
    for row in cursor:
        total = row[1]
        valid = row[2]
        volume_valid = row[3]
        
        price_score = (valid / total * 100) if total > 0 else 0
        volume_score = (volume_valid / total * 100) if total > 0 else 0
        overall_score = (price_score * 0.7 + volume_score * 0.3)
        
        scores.append({
            'symbol': row[0],
            'total_days': total,
            'price_score': round(price_score, 2),
            'volume_score': round(volume_score, 2),
            'overall_score': round(overall_score, 2)
        })
    
    cursor.close()
    return scores

def main():
    logger.info("="*70)
    logger.info("DATA QUALITY CHECK - STARTED")
    logger.info("="*70)
    
    conn = connect_db()
    all_issues = []
    
    logger.info("Checking for zero/null prices...")
    zero_issues = check_zero_prices(conn)
    if zero_issues:
        logger.warning(f"Found {len(zero_issues)} zero/null price records")
        for issue in zero_issues:
            logger.warning(f"  {issue[0]}: {issue[1]}")
            all_issues.append(('ZERO_PRICE', issue[0], str(issue), 'HIGH'))
    
    logger.info("Checking for missing trading days...")
    gap_issues = check_missing_trading_days(conn)
    if gap_issues:
        logger.warning(f"Found {len(gap_issues)} large gaps")
        for issue in gap_issues[:20]:
            logger.warning(f"  {issue['symbol']}: Gap of {issue['gap_days']} days")
            all_issues.append(('LARGE_GAP', issue['symbol'], 
                            f"Gap of {issue['gap_days']} days", 'MEDIUM'))
    
    logger.info("Checking for price anomalies...")
    price_issues = check_price_gaps(conn, 20)
    if price_issues:
        logger.warning(f"Found {len(price_issues)} large price changes")
        for issue in price_issues[:20]:
            logger.warning(f"  {issue[0]}: Change: {issue[4]}%")
            all_issues.append(('PRICE_GAP', issue[0], 
                            f"Price change {issue[4]}%", 'HIGH'))
    
    logger.info("Checking for volume anomalies...")
    volume_issues = check_volume_anomalies(conn)
    if volume_issues:
        logger.warning(f"Found {len(volume_issues)} zero volume records")
        for issue in volume_issues[:20]:
            logger.warning(f"  {issue[0]}: {issue[1]}")
            all_issues.append(('ZERO_VOLUME', issue[0], str(issue), 'MEDIUM'))
    
    logger.info("Checking for duplicate entries...")
    dup_issues = check_duplicate_dates(conn)
    if dup_issues:
        logger.error(f"Found {len(dup_issues)} duplicate entries!")
        for issue in dup_issues:
            logger.error(f"  {issue[0]}: {issue[1]} - Count: {issue[2]}")
            all_issues.append(('DUPLICATE', issue[0], str(issue), 'CRITICAL'))
    
    logger.info("Logging issues to database...")
    for issue_type, symbol, details, severity in all_issues:
        log_quality_issue(conn, issue_type, symbol, details, severity)
    
    logger.info("Calculating quality scores...")
    scores = generate_quality_score(conn)
    low_quality = [s for s in scores if s['overall_score'] < 99]
    if low_quality:
        logger.warning(f"Found {len(low_quality)} stocks with quality score < 99%")
    
    conn.close()
    
    logger.info("="*70)
    logger.info("DATA QUALITY CHECK - COMPLETED")
    logger.info("="*70)
    logger.info(f"Total issues: {len(all_issues)}")
    
    return 0 if len([i for i in all_issues if i[3] in ['HIGH', 'CRITICAL']]) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())