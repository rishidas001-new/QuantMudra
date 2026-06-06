# QuantMudra

**NSE India Stock Data Pipeline** - Automated daily data acquisition system for Nifty 500 stocks with Oracle ATP database.

## 📋 Overview

QuantMudra is a production-ready data pipeline that fetches, stores, and maintains historical OHLCV (Open, High, Low, Close, Volume) data for 500+ NSE India stocks from 2016 to present.

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Yahoo Finance  │────▶│   Python ETL    │────▶│  Oracle ATP     │
│  (Data Source)  │     │   (Pipeline)    │     │  (Database)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │   Cron Jobs     │
                        │  (Scheduler)    │
                        └─────────────────┘
```

## 📁 Project Structure

```
QuantMudra/
├── docs/                    # Architecture documents
├── quantmudra/
│   ├── data_pipeline/       # Core pipeline scripts
│   │   ├── update_daily.py   # Daily OHLCV fetcher
│   │   ├── check_quality.py # Data quality validator
│   │   ├── process_corp_actions.py  # Splits/dividends
│   │   └── generate_quality_report.py
│   ├── setup/               # Setup scripts
│   │   └── setup_cron.sh    # Cron scheduler
│   └── scripts/             # Utility scripts
├── sql/                     # Database schema
└── config/                 # Configuration
```

## 🚀 Quick Start

```bash
# Install dependencies
pip install oracledb yfinance pandas

# Run daily update
python3 quantmudra/update_daily.py

# Run quality check
python3 quantmudra/check_quality.py
```

## 📊 Database Schema

| Table | Description |
|-------|-------------|
| STOCK_OHLCV_DAILY | Daily OHLCV price data |
| STOCK_MASTER | Stock reference data |
| INDEX_CONSTITUENTS | Nifty index composition |
| CORPORATE_ACTIONS | Splits and dividends |
| STOCK_PRICE_METADATA | Data quality stats |

## ⏰ Scheduled Jobs

| Job | Schedule | Time (IST) |
|-----|----------|------------|
| Daily Update | Weekdays | 6:30 PM |
| Quality Check | Weekdays | 8:00 PM |
| Corp Actions | Daily | 7:00 AM |
| Index Update | Monday | 3:00 AM |
| Quality Report | Sunday | 6:00 PM |

## 📈 Current Data

- **Total Records:** 1,030,345+
- **Total Stocks:** 500
- **Date Range:** 2016-01-01 to present
- **Sectors:** 11 (Financial Services, Technology, Healthcare, etc.)

## 🔧 Configuration

```python
DB_CONFIG = {
    'user': 'admin',
    'dsn': 'quantmudra_high',
    'wallet_location': '/path/to/wallet'
}
```

## 📄 License

MIT License
