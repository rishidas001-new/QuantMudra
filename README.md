# QuantMudra - NSE India Stock Data Pipeline

> **Automated daily data acquisition system for Nifty 500 stocks with Oracle ATP database**

---

## 🎯 Original Requirements

| Requirement | Status | Details |
|-------------|--------|---------|
| Fetch Nifty 500 stock data | ✅ Complete | 500 stocks from NSE |
| Historical data from 2016 | ✅ Complete | 9+ years of data |
| Daily automated updates | ✅ Complete | Cron scheduled |
| Oracle ATP database | ✅ Complete | Wallet authentication |
| Corporate actions handling | ✅ Complete | Splits, dividends, bonuses |
| Data quality checks | ✅ Complete | Automated validation |

---

## 🔧 Adjustments Made

### 1. Cron Schedule Fix
**Problem:** Corporate actions were scheduled monthly, but they happen daily.

**Solution:** Changed all cron schedules to daily execution:

| Script | Original | Fixed |
|--------|----------|-------|
| `update_daily.py` | Monthly | **Daily (Weekdays 6:30 PM IST)** |
| `process_corp_actions.py` | Monthly | **Daily (7:00 AM IST)** |
| `check_quality.py` | Monthly | **Daily (Weekdays 8:00 PM IST)** |
| `update_index_composition.py` | Monthly | **Weekly (Monday 3:00 AM IST)** |
| `generate_quality_report.py` | Monthly | **Weekly (Sunday 6:00 PM IST)** |

### 2. Oracle Column Size Fix
**Problem:** NSE symbols have `.NS` suffix (e.g., `RELIANCE.NS`), exceeding 10-character Oracle column limit.

**Solution:** Stripped `.NS` suffix during data ingestion:
```python
symbol = ticker.replace('.NS', '')  # RELIANCE.NS → RELIANCE
```

### 3. STOCK_MASTER NULL Fix
**Problem:** Stock master table had NULL values in sector, industry, and market_cap fields.

**Solution:** Updated all 500 records using yfinance:
```python
stock = yf.Ticker(f"{symbol}.NS")
info = stock.info
# Update sector, industry, market_cap for all stocks
```

---

## 📊 Database Schema

### Core Tables

| Table | Rows | Description |
|-------|------|-------------|
| `STOCK_MASTER` | 500 | Stock reference data (symbol, name, sector, industry, market_cap) |
| `STOCK_OHLCV_DAILY` | 1,030,000+ | Daily OHLCV price data |
| `INDEX_CONSTITUENTS` | 64 | Nifty 50/100/500 composition |
| `CORPORATE_ACTIONS` | 938 | Splits, dividends, bonuses |
| `STOCK_PRICE_METADATA` | 500 | Data quality statistics |
| `JOB_EXECUTION_LOG` | - | **Job run tracking with statistics** |

### JOB_EXECUTION_LOG Table

Tracks all scheduled job executions with detailed statistics:

| Column | Type | Description |
|--------|------|-------------|
| LOG_ID | NUMBER | Auto-generated primary key |
| JOB_NAME | VARCHAR2(50) | Script name (e.g., update_daily) |
| JOB_TYPE | VARCHAR2(30) | Category (DAILY_UPDATE, QUALITY_CHECK, etc.) |
| START_TIME | TIMESTAMP | Job start time |
| END_TIME | TIMESTAMP | Job end time |
| STATUS | VARCHAR2(20) | RUNNING, SUCCESS, FAILED, PARTIAL |
| RECORDS_ADDED | NUMBER | New records inserted |
| RECORDS_UPDATED | NUMBER | Existing records modified |
| RECORDS_FAILED | NUMBER | Records that failed |
| ERROR_MESSAGE | VARCHAR2(2000) | Error details if failed |
| DURATION_SECONDS | NUMBER | Total execution time |

### Views for Quick Monitoring

```sql
-- Last run status for each job
SELECT * FROM V_JOB_LAST_RUN;

-- Daily summary statistics
SELECT * FROM V_DAILY_JOB_SUMMARY;
```

### Example Query - Check Job Status
```sql
SELECT JOB_NAME, START_TIME, STATUS, RECORDS_ADDED, RECORDS_UPDATED, DURATION_SECONDS
FROM V_JOB_LAST_RUN
ORDER BY START_TIME DESC;
```

### Example Query - Today's Runs
```sql
SELECT * FROM JOB_EXECUTION_LOG 
WHERE TRUNC(START_TIME) = TRUNC(SYSDATE)
ORDER BY START_TIME DESC;
```

---

## 📁 Project Structure

```
QuantMudra/
├── docs/                          # Architecture documents
├── quantmudra/
│   ├── data_pipeline/
│   │   ├── update_daily.py              # Daily OHLCV data fetcher (+ logging)
│   │   ├── check_quality.py             # Data quality validator
│   │   ├── process_corp_actions.py     # Handle splits/dividends
│   │   ├── update_index_composition.py  # Update index constituents
│   │   └── generate_quality_report.py  # Weekly quality report
│   ├── scripts/
│   │   ├── job_logger.py               # Job execution logging utility
│   │   └── ...
│   ├── setup/
│   │   └── setup_cron.sh                # Cron scheduler
│   └── sql/
│       └── create_job_execution_log.sql # Log table schema
└── README.md                            # This file
```

---

## 🚀 Installation & Setup

### Prerequisites
```bash
pip install oracledb yfinance pandas numpy
```

### Oracle ATP Configuration
```python
DB_CONFIG = {
    'user': 'admin',
    'dsn': 'quantmudra_high',
    'wallet_location': '/path/to/Wallet_QuantMudra'
}
```

---

## 📅 Scheduled Jobs

| Script | Schedule | Time (IST) |
|--------|----------|------------|
| update_daily.py | Weekdays | 6:30 PM |
| process_corp_actions.py | Daily | 7:00 AM |
| check_quality.py | Weekdays | 8:00 PM |
| update_index_composition.py | Monday | 3:00 AM |
| generate_quality_report.py | Sunday | 6:00 PM |

---

## 📊 Data Quality Metrics

| Metric | Value |
|--------|-------|
| Total Records | 1,030,345+ |
| Date Range | 2016-01-01 to 2026-05-31 |
| Stocks Covered | 500 |
| Sectors | 11 |
| Data Completeness | >99.5% |

---

## 📈 Sector Distribution

| Sector | Count |
|--------|-------|
| Financial Services | 85 |
| Technology | 62 |
| Healthcare | 45 |
| Manufacturing | 42 |
| Others | 266 |

---

## 🔍 Usage

```bash
# Daily update
python3 quantmudra/data_pipeline/update_daily.py

# Quality check
python3 quantmudra/data_pipeline/check_quality.py

# Process corporate actions
python3 quantmudra/data_pipeline/process_corp_actions.py
```

---

## 📝 Maintenance

### Log Files
```bash
/workspace/quantmudra/logs/
```

---

## 🔗 Links

- **Repository:** https://github.com/rishidas001-new/QuantMudra
- **Oracle Cloud:** https://cloud.oracle.com
- **NSE India:** https://www.nseindia.com

---

## 📄 License

MIT License
