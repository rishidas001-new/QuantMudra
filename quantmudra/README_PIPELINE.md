# QuantMudra Data Pipeline

## 📋 Overview

Automated data pipeline for NSE Nifty 500 stock data with Oracle ATP database.

## 📁 Scripts

| Script | Purpose | Frequency |
|--------|---------|-----------|
| `update_daily.py` | Fetch daily OHLCV data from Yahoo Finance | Daily (weekdays 6:30 PM IST) |
| `check_quality.py` | Validate data quality (zero prices, gaps, anomalies) | Daily (weekdays 8:00 PM IST) |
| `process_corp_actions.py` | Handle stock splits and dividends | Daily (7:00 AM) |
| `update_index_composition.py` | Track Nifty index changes and IPOs | Weekly (Monday 3:00 AM) |
| `generate_quality_report.py` | Generate weekly quality reports | Weekly (Sunday 6:00 PM) |

## 🚀 Quick Start

### Manual Execution

```bash
cd /workspace/quantmudra

# Daily update
python3 update_daily.py

# Quality check
python3 check_quality.py

# Generate report
python3 generate_quality_report.py
```

### Cron Setup

Run the setup script:
```bash
./setup_cron.sh
```

## 📊 Database Schema

### Tables

- `STOCK_OHLCV_DAILY` - Daily OHLCV price data
- `STOCK_MASTER` - Stock reference data
- `INDEX_COMPOSITION` - Nifty index constituents
- `CORPORATE_ACTIONS` - Splits and dividends log
- `DATA_REFRESH_LOG` - Update run history
- `DATA_QUALITY_LOG` - Quality issues log

## 📁 Directory Structure

```
/workspace/quantmudra/
├── update_daily.py           # Daily data fetcher
├── check_quality.py          # Quality validator
├── process_corp_actions.py   # Corporate actions
├── update_index_composition.py # Index tracker
├── generate_quality_report.py # Report generator
├── setup_cron.sh            # Cron setup script
├── cron_schedule.txt        # Cron schedule file
├── logs/                    # Log files
│   ├── update_daily.log
│   ├── check_quality.log
│   ├── corp_actions.log
│   ├── index_composition.log
│   └── quality_report.log
└── reports/                  # Generated reports
    ├── quality_report.csv
    └── quality_report.json
```

## 🔧 Configuration

Database connection settings in each script:
```python
DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}
```

## 📅 Cron Schedule

| Script | Schedule | Time (IST) |
|--------|----------|------------|
| update_daily.py | `30 13 * * 1-5` | 6:30 PM Mon-Fri |
| check_quality.py | `0 14 * * 1-5` | 8:00 PM Mon-Fri |
| generate_quality_report.py | `0 12 * * 0` | 6:00 PM Sunday |
| process_corp_actions.py | `0 1 * * *` | 7:00 AM Daily |
| update_index_composition.py | `0 21 * * 1` | 3:00 AM Monday |

## 📈 Current Data Status

- **Total Records:** 1,030,345+
- **Total Stocks:** 500
- **Date Range:** 2016-01-01 to 2026-06-05
- **Stocks with 2016 data:** 318

## 🔍 Quality Checks

The `check_quality.py` script validates:
- Zero or null prices
- Missing trading days (gaps > 5 days)
- Large price changes (>20%)
- Zero volume records
- Duplicate date entries

## 📝 Logs

All logs are stored in `/workspace/quantmudra/logs/`

View recent logs:
```bash
tail -50 logs/update_daily.log
tail -50 logs/check_quality.log
```

## 🚨 Troubleshooting

### Database Connection Failed
```bash
# Verify wallet exists
ls -la /home/openhands/.oci/quantmudra_wallet/

# Test connection
python3 -c "import oracledb; print('OK')"
```

### Missing Modules
```bash
pip install oracledb yfinance pandas
```

### Cron Not Running
```bash
# View current crontab
crontab -l

# Reinstall cron jobs
crontab /workspace/quantmudra/cron_schedule.txt
```

## 📊 Report Output

Reports are generated in:
- `/workspace/quantmudra/reports/quality_report.csv` - CSV format
- `/workspace/quantmudra/reports/quality_report.json` - JSON format

## 🔄 Manual Workflow

1. **Initial Setup:**
   ```bash
   python3 process_corp_actions.py  # Process historical corporate actions
   python3 update_index_composition.py  # Sync index composition
   ```

2. **Daily Operations:**
   ```bash
   python3 update_daily.py  # Fetch today's data
   python3 check_quality.py  # Validate quality
   ```

3. **Weekly/Monthly:**
   ```bash
   python3 generate_quality_report.py  # Generate report
   ```

## 📞 Support

For issues or questions, check:
1. Log files in `/workspace/quantmudra/logs/`
2. Oracle ATP console for database status
3. Yahoo Finance API status