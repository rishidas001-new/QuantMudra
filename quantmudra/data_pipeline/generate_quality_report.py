#!/usr/bin/env python3
"""
Quality Report Generator
Generates weekly/monthly data quality reports
Sends alerts for data failures
"""
import oracledb
from datetime import datetime, date, timedelta
import sys
import logging
import csv
import json

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/workspace/quantmudra/logs/quality_report.log'),
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

def get_database_summary(conn):
    """Get overall database statistics"""
    cursor = conn.cursor()
    
    stats = {}
    
    cursor.execute("SELECT COUNT(*) FROM admin.stock_ohlcv_daily")
    stats['total_records'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT symbol) FROM admin.stock_ohlcv_daily")
    stats['total_stocks'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM admin.stock_ohlcv_daily")
    min_dt, max_dt = cursor.fetchone()
    stats['date_range'] = f"{min_dt.strftime('%Y-%m-%d')} to {max_dt.strftime('%Y-%m-%d')}"
    stats['days_of_data'] = (max_dt.date() - min_dt.date()).days
    
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT symbol FROM admin.stock_ohlcv_daily
            GROUP BY symbol
            HAVING MIN(trade_date) >= DATE '2016-01-01' AND MIN(trade_date) < DATE '2016-02-01'
        )
    """)
    stats['stocks_2016'] = cursor.fetchone()[0]
    
    cursor.close()
    return stats

def get_quality_scores(conn):
    """Calculate quality scores for all stocks"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as total_days,
            SUM(CASE WHEN close_price > 0 THEN 1 ELSE 0 END) as valid_prices,
            SUM(CASE WHEN volume > 0 THEN 1 ELSE 0 END) as valid_volume,
            MIN(trade_date) as first_date,
            MAX(trade_date) as last_date
        FROM admin.stock_ohlcv_daily
        GROUP BY symbol
        ORDER BY symbol
    """)
    
    scores = []
    for row in cursor:
        total = row[1]
        valid_price = row[2]
        valid_vol = row[3]
        
        price_score = round((valid_price / total * 100) if total > 0 else 0, 2)
        volume_score = round((valid_vol / total * 100) if total > 0 else 0, 2)
        overall = round(price_score * 0.7 + volume_score * 0.3, 2)
        
        scores.append({
            'symbol': row[0],
            'total_days': total,
            'price_score': price_score,
            'volume_score': volume_score,
            'overall_score': overall,
            'first_date': row[4],
            'last_date': row[5]
        })
    
    cursor.close()
    return scores

def get_recent_issues(conn, days=7):
    """Get recent quality issues"""
    cursor = conn.cursor()
    cutoff = date.today() - timedelta(days=days)
    
    cursor.execute("""
        SELECT issue_type, symbol, details, severity, created_at
        FROM admin.data_quality_log
        WHERE check_date >= :1
        ORDER BY created_at DESC
    """, [cutoff])
    
    issues = []
    for row in cursor:
        issues.append({
            'type': row[0],
            'symbol': row[1],
            'details': row[2],
            'severity': row[3],
            'date': row[4]
        })
    
    cursor.close()
    return issues

def get_update_history(conn, days=30):
    """Get recent update history"""
    cursor = conn.cursor()
    cutoff = date.today() - timedelta(days=days)
    
    cursor.execute("""
        SELECT refresh_date, total_stocks, success_count, failed_count, 
               records_updated, status, created_at
        FROM admin.data_refresh_log
        WHERE refresh_date >= :1
        ORDER BY refresh_date DESC
    """, [cutoff])
    
    history = []
    for row in cursor:
        history.append({
            'date': row[0],
            'total': row[1],
            'success': row[2],
            'failed': row[3],
            'records': row[4],
            'status': row[5],
            'created': row[6]
        })
    
    cursor.close()
    return history

def generate_text_report(summary, scores, issues, history):
    """Generate plain text report"""
    report = []
    report.append("=" * 70)
    report.append("QUANTMUDRA DATA QUALITY REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 70)
    
    # Summary
    report.append("\n📊 DATABASE SUMMARY")
    report.append("-" * 40)
    report.append(f"  Total Records:     {summary['total_records']:,}")
    report.append(f"  Total Stocks:       {summary['total_stocks']}")
    report.append(f"  Date Range:         {summary['date_range']}")
    report.append(f"  Days of Data:       {summary['days_of_data']}")
    report.append(f"  Stocks from 2016:   {summary['stocks_2016']}")
    
    # Quality scores
    report.append("\n📈 QUALITY SCORES")
    report.append("-" * 40)
    
    low_quality = [s for s in scores if s['overall_score'] < 95]
    good_quality = [s for s in scores if s['overall_score'] >= 99]
    
    report.append(f"  Excellent (99%+):    {len([s for s in scores if s['overall_score'] >= 99])}")
    report.append(f"  Good (95-99%):      {len([s for s in scores if 95 <= s['overall_score'] < 99])}")
    report.append(f"  Needs Attention:    {len(low_quality)}")
    
    if low_quality:
        report.append("\n  ⚠️  Stocks needing attention:")
        for s in low_quality[:10]:
            report.append(f"     {s['symbol']}: {s['overall_score']}%")
    
    # Recent issues
    if issues:
        report.append("\n🚨 RECENT ISSUES (Last 7 days)")
        report.append("-" * 40)
        report.append(f"  Total issues: {len(issues)}")
        
        by_severity = {}
        for i in issues:
            by_severity[i['severity']] = by_severity.get(i['severity'], 0) + 1
        
        for sev, count in sorted(by_severity.items()):
            report.append(f"    {sev}: {count}")
    
    # Update history
    if history:
        report.append("\n📅 UPDATE HISTORY (Last 30 days)")
        report.append("-" * 40)
        success_days = len([h for h in history if h['status'] == 'COMPLETED'])
        failed_days = len(history) - success_days
        report.append(f"  Total update runs: {len(history)}")
        report.append(f"  Successful: {success_days}")
        report.append(f"  Failed: {failed_days}")
        
        if history:
            latest = history[0]
            report.append(f"\n  Latest update ({latest['date'].strftime('%Y-%m-%d')}):")
            report.append(f"    Records: {latest['records']:,}")
            report.append(f"    Status: {latest['status']}")
    
    report.append("\n" + "=" * 70)
    report.append("END OF REPORT")
    report.append("=" * 70)
    
    return "\n".join(report)

def generate_csv_report(scores, filename='quality_report.csv'):
    """Generate CSV quality report"""
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'symbol', 'total_days', 'price_score', 'volume_score', 
            'overall_score', 'first_date', 'last_date'
        ])
        writer.writeheader()
        for score in scores:
            writer.writerow(score)
    
    logger.info(f"CSV report saved to {filename}")

def generate_json_report(summary, scores, issues, history, filename='quality_report.json'):
    """Generate JSON report"""
    report = {
        'generated_at': datetime.now().isoformat(),
        'summary': summary,
        'quality_scores': scores,
        'recent_issues': issues,
        'update_history': history
    }
    
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info(f"JSON report saved to {filename}")

def main():
    logger.info("="*70)
    logger.info("QUALITY REPORT GENERATOR - STARTED")
    logger.info("="*70)
    
    try:
        conn = connect_db()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
    
    # Gather data
    logger.info("Gathering database summary...")
    summary = get_database_summary(conn)
    
    logger.info("Calculating quality scores...")
    scores = get_quality_scores(conn)
    
    logger.info("Fetching recent issues...")
    issues = get_recent_issues(conn, 7)
    
    logger.info("Fetching update history...")
    history = get_update_history(conn, 30)
    
    conn.close()
    
    # Generate reports
    logger.info("Generating text report...")
    text_report = generate_text_report(summary, scores, issues, history)
    print(text_report)
    
    logger.info("Generating CSV report...")
    generate_csv_report(scores, '/workspace/quantmudra/reports/quality_report.csv')
    
    logger.info("Generating JSON report...")
    generate_json_report(summary, scores, issues, history, 
                        '/workspace/quantmudra/reports/quality_report.json')
    
    logger.info("="*70)
    logger.info("QUALITY REPORT GENERATOR - COMPLETED")
    logger.info("="*70)
    
    return 0

if __name__ == "__main__":
    # Create reports directory if not exists
    import os
    os.makedirs('/workspace/quantmudra/reports', exist_ok=True)
    
    sys.exit(main())