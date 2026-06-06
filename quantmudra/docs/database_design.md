# QuantMudra NSE 360° Analytical Platform
## Database Design Document v1.0

---

## 1. Executive Summary

This document outlines the complete database architecture for the QuantMudra NSE 360° Analytical Platform, designed to store and manage 10+ years of daily OHLCV data for Nifty 500+ stocks with supporting reference data.

### Key Objectives
- Store daily OHLCV data for 500+ NSE stocks (5-10 year history)
- Support incremental daily updates (new trading day data)
- Track data quality and refresh history
- Enable corporate actions processing (splits, bonuses, dividends)
- Support index composition tracking (Nifty 50, Nifty 500, F&O)

---

## 2. Current Database Schema

### 2.1 Core Tables (Existing)

#### STOCK_OHLCV_DAILY - Primary Price Data Table
```
┌─────────────────────────────────────────────────────────────────┐
│                    STOCK_OHLCV_DAILY                           │
├─────────────────────────────────────────────────────────────────┤
│ ID              NUMBER(22)     PK, NOT NULL                     │
│ SYMBOL          VARCHAR2(50)   NOT NULL                         │
│ TRADE_DATE      DATE           NOT NULL                         │
│ OPEN_PRICE      NUMBER(22)                                     │
│ HIGH_PRICE      NUMBER(22)                                     │
│ LOW_PRICE       NUMBER(22)                                      │
│ CLOSE_PRICE     NUMBER(22)                                      │
│ ADJ_CLOSE       NUMBER(22)     ← Adjusted for corporate actions│
│ VOLUME          NUMBER(22)                                      │
│ NSE_SYMBOL      VARCHAR2(50)   (e.g., NSE:RELIANCE-EQ)        │
│ SOURCE          VARCHAR2(20)   (YAHOO/FYERS/NSE)              │
│ CREATED_AT      TIMESTAMP(6)                                   │
│ UPDATED_AT      TIMESTAMP(6)                                   │
└─────────────────────────────────────────────────────────────────┘

UNIQUE CONSTRAINT: (SYMBOL, TRADE_DATE)
```

#### STOCK_MASTER - Reference Data
```
┌─────────────────────────────────────────────────────────────────┐
│                      STOCK_MASTER                               │
├─────────────────────────────────────────────────────────────────┤
│ SYMBOL              VARCHAR2(50)   PK, NOT NULL                │
│ COMPANY_NAME        VARCHAR2(200)                                 │
│ SECTOR              VARCHAR2(100)                                 │
│ INDUSTRY            VARCHAR2(100)                                 │
│ MARKET_CAP_CATEGORY VARCHAR2(50)  (LARGE/MID/SMALL)            │
│ IS_ACTIVE          NUMBER(1)     (1=ACTIVE, 0=INACTIVE)        │
│ CREATED_AT          TIMESTAMP(6)                                 │
│ UPDATED_AT          TIMESTAMP(6)                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### STOCK_PRICE_METADATA - Data Quality Tracking
```
┌─────────────────────────────────────────────────────────────────┐
│                  STOCK_PRICE_METADATA                           │
├─────────────────────────────────────────────────────────────────┤
│ METADATA_ID        NUMBER(22)   PK, NOT NULL                   │
│ SYMBOL              VARCHAR2(50)                                 │
│ EXCHANGE            VARCHAR2(20)                                │
│ SERIES              VARCHAR2(20)   (EQ, BE, BL, etc.)          │
│ MIN_DATE            DATE                                         │
│ MAX_DATE            DATE                                         │
│ TOTAL_RECORDS       NUMBER                                       │
│ LAST_REFRESH_DATE   TIMESTAMP(6)                                 │
│ DATA_QUALITY_SCORE  NUMBER(5,2)  (0.00 - 100.00)              │
└─────────────────────────────────────────────────────────────────┘
```

#### DATA_REFRESH_LOG - Pipeline Audit Trail
```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA_REFRESH_LOG                             │
├─────────────────────────────────────────────────────────────────┤
│ REFRESH_ID          NUMBER(22)   PK, NOT NULL                   │
│ SYMBOL              VARCHAR2(50)                                 │
│ DATA_TYPE           VARCHAR2(50)  (OHLCV/CORP_ACTION/INDEX)     │
│ START_DATE          DATE                                         │
│ END_DATE            DATE                                         │
│ RECORD_COUNT        NUMBER                                       │
│ STATUS              VARCHAR2(20)  (SUCCESS/FAILED/PARTIAL)      │
│ ERROR_MESSAGE       VARCHAR2(2000)                               │
│ REFRESH_TIMESTAMP   TIMESTAMP(6)                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### CORPORATE_ACTIONS - Splits, Dividends, Bonuses
```
┌─────────────────────────────────────────────────────────────────┐
│                   CORPORATE_ACTIONS                             │
├─────────────────────────────────────────────────────────────────┤
│ ID                  NUMBER(22)   PK, NOT NULL                   │
│ SYMBOL              VARCHAR2(50)   NOT NULL                     │
│ ACTION_DATE         DATE           NOT NULL                     │
│ ACTION_TYPE         VARCHAR2(50)   NOT NULL                     │
│                     → SPLIT, BONUS, DIVIDEND, RIGHTS           │
│ RATIO               NUMBER(10,4)   (e.g., 2 for 1 split)       │
│ AMOUNT              NUMBER(15,4)   (e.g., dividend per share)  │
│ CREATED_AT          TIMESTAMP(6)                               │
└─────────────────────────────────────────────────────────────────┘
```

#### INDEX_CONSTITUENTS - Index Membership History
```
┌─────────────────────────────────────────────────────────────────┐
│                   INDEX_CONSTITUENTS                            │
├─────────────────────────────────────────────────────────────────┤
│ ID                  NUMBER(22)   PK, NOT NULL                   │
│ INDEX_SYMBOL         VARCHAR2(50)  (NIFTY50, NIFTY500, NIFTY100) │
│ STOCK_SYMBOL         VARCHAR2(50)                               │
│ EFFECTIVE_DATE       DATE                                         │
│ END_DATE             DATE          (NULL = currently active)     │
│ IS_CONSTITUENT       NUMBER(1)     (1=YES, 0=NO)               │
│ CREATED_AT           TIMESTAMP(6)                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Proposed New Tables

### 3.1 Intraday Data Store (For Future Use)
```sql
CREATE TABLE STOCK_OHLCV_INTRADAY (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    SYMBOL          VARCHAR2(50) NOT NULL,
    TRADESTAMP      TIMESTAMP NOT NULL,
    OPEN_PRICE      NUMBER(22,4),
    HIGH_PRICE      NUMBER(22,4),
    LOW_PRICE       NUMBER(22,4),
    CLOSE_PRICE     NUMBER(22,4),
    VOLUME          NUMBER(22),
    INTERVAL_MIN    NUMBER(5) NOT NULL,  -- 1, 5, 15, 30, 60
    SOURCE          VARCHAR2(20),
    CREATED_AT      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (SYMBOL, TRADESTAMP, INTERVAL_MIN)
);
```

### 3.2 Market Holidays Calendar
```sql
CREATE TABLE MARKET_HOLIDAYS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    TRADE_DATE      DATE NOT NULL UNIQUE,
    EXCHANGE        VARCHAR2(20) NOT NULL,  -- NSE, BSE
    DESCRIPTION     VARCHAR2(100),
    IS_TRADING_DAY  NUMBER(1) NOT NULL DEFAULT 0
);
```

### 3.3 F&O Instrument Metadata
```sql
CREATE TABLE FO_INSTRUMENTS (
    SYMBOL          VARCHAR2(50) PRIMARY KEY,
    TOKEN           NUMBER,
    NAME            VARCHAR2(200),
    INSTRUMENT_TYPE VARCHAR2(20),  -- CE, PE, FUT, STOCK
    EXPIRY_DATE     DATE,
    STRIKE_PRICE    NUMBER,
    LOT_SIZE        NUMBER,
    UNDERLYING      VARCHAR2(50),
    IS_ACTIVE       NUMBER(1) DEFAULT 1,
    CREATED_AT      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 Data Quality Issues Log
```sql
CREATE TABLE DATA_QUALITY_LOG (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    SYMBOL          VARCHAR2(50) NOT NULL,
    TRADE_DATE      DATE,
    ISSUE_TYPE      VARCHAR2(50),  -- MISSING_DATA, PRICE_ZERO, VOLUME_ZERO
    ISSUE_DETAILS   VARCHAR2(500),
    SEVERITY        VARCHAR2(20),  -- LOW, MEDIUM, HIGH
    RESOLVED        NUMBER(1) DEFAULT 0,
    RESOLUTION_NOTES VARCHAR2(500),
    CREATED_AT      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    RESOLVED_AT     TIMESTAMP
);
```

---

## 4. Index Strategy

### Recommended Indexes
```sql
-- Primary lookup (already exists as unique constraint)
CREATE UNIQUE INDEX idx_ohlcv_symbol_date ON STOCK_OHLCV_DAILY(SYMBOL, TRADE_DATE);

-- Date range queries (historical analysis)
CREATE INDEX idx_ohlcv_trade_date ON STOCK_OHLCV_DAILY(TRADE_DATE);

-- Symbol list queries (multiple stocks)
CREATE INDEX idx_ohlcv_symbol ON STOCK_OHLCV_DAILY(SYMBOL);

-- Composite for sector analysis
CREATE INDEX idx_ohlcv_sector ON STOCK_MASTER(SECTOR);

-- Refresh tracking
CREATE INDEX idx_refresh_symbol ON DATA_REFRESH_LOG(SYMBOL, REFRESH_TIMESTAMP DESC);
```

---

## 5. Data Acquisition Architecture

### 5.1 Historical Data Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HISTORICAL DATA ACQUISITION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│  │  NSE 500     │    │  F&O List    │    │  Indices     │                │
│  │  Symbols     │    │  (200+ stocks)│    │  (NIFTY50/500)│                │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
│         │                   │                    │                          │
│         └───────────────────┼────────────────────┘                          │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    SYMBOL MASTER TABLE                               │  │
│  │                 (STOCK_MASTER + F&O_INSTRUMENTS)                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                   DATA SOURCE SELECTION                              │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   │  │
│  │  │  Yahoo Finance  │    │   NSE Bhav Copy │    │   Alpha Vantage │   │  │
│  │  │  (Primary)      │    │   (Backup)      │    │   (Alternative) │   │  │
│  │  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘   │  │
│  └──────────┼───────────────────────┼───────────────────────┼────────────┘  │
│             │                       │                       │               │
│             ▼                       ▼                       ▼               │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        EXTRACTION LAYER                             │  │
│  │                                                                      │  │
│  │   • Download 5-10 years of daily data                               │  │
│  │   • Validate OHLCV integrity                                        │  │
│  │   • Handle missing data points                                      │  │
│  │   • Apply corporate actions adjustments                             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      TRANSFORM LAYER                                │  │
│  │                                                                      │  │
│  │   • Standardize symbol format                                        │  │
│  │   • Convert timezone (UTC → Asia/Kolkata)                           │  │
│  │   • Calculate derived metrics (returns, volatility)                │  │
│  │   • Flag data quality issues                                        │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        LOAD LAYER                                   │  │
│  │                                                                      │  │
│  │   • MERGE (upsert) to prevent duplicates                           │  │
│  │   • Batch insert for performance (1000 rows/batch)                  │  │
│  │   • Update metadata table                                           │  │
│  │   • Log refresh operation                                           │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    ORACLE ATP DATABASE                              │  │
│  │                                                                      │  │
│  │   STOCK_OHLCV_DAILY  (Current: 18,717 records, 15 stocks)           │  │
│  │   Target: ~620,000 records (504 stocks × 5 years × ~1,230 days)    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Incremental (Daily) Update Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DAILY INCREMENTAL UPDATE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    6:00 PM IST    ┌──────────────┐                       │
│  │   CRON      │ ─────────────────► │   TRIGGER   │                       │
│  │  Scheduler  │                    │   SCRIPT    │                       │
│  └──────────────┘                   └──────┬───────┘                       │
│                                           │                                │
│                                           ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      STEP 1: CHECK MARKET STATUS                     │  │
│  │                                                                      │  │
│  │   • Is today a trading day? (check MARKET_HOLIDAYS)                 │  │
│  │   • Market closed? (NSE - 3:30 PM IST)                              │  │
│  │   • Bhav copy available? (usually 6:00 PM)                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                           │                                │
│                                           ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                     STEP 2: FETCH LATEST DATA                       │  │
│  │                                                                      │  │
│  │   For each active stock:                                            │  │
│  │   • Get last stored date from STOCK_PRICE_METADATA                  │  │
│  │   • Download data from last date + 1 to today                       │  │
│  │   • Use Yahoo Finance: ticker + "?period1=X&period2=Y"              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                           │                                │
│                                           ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      STEP 3: VALIDATE DATA                           │  │
│  │                                                                      │  │
│  │   • Check all OHLC fields present                                    │  │
│  │   • Verify HIGH >= LOW                                               │  │
│  │   • Verify prices > 0                                                │  │
│  │   • Flag anomalies to DATA_QUALITY_LOG                               │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                           │                                │
│                                           ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                       STEP 4: UPSERT DATA                            │  │
│  │                                                                      │  │
│  │   MERGE INTO stock_ohlcv_daily                                       │  │
│  │   USING (SELECT :sym, :dt FROM dual) s                               │  │
│  │   ON (symbol = s.sym AND trade_date = s.dt)                         │  │
│  │   WHEN MATCHED THEN UPDATE                                           │  │
│  │   WHEN NOT MATCHED THEN INSERT                                       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                           │                                │
│                                           ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                       STEP 5: UPDATE METADATA                        │  │
│  │                                                                      │  │
│  │   • Update MAX_DATE in STOCK_PRICE_METADATA                         │  │
│  │   • Increment TOTAL_RECORDS                                         │  │
│  │   • Update LAST_REFRESH_DATE                                         │  │
│  │   • Log to DATA_REFRESH_LOG                                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         ERROR HANDLING                              │  │
│  │                                                                      │  │
│  │   • Retry 3 times on network failure                                 │  │
│  │   • Log failed symbols to DATA_REFRESH_LOG                           │  │
│  │   • Send alert if >10% symbols fail                                  │  │
│  │   • Continue with remaining stocks                                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Acquisition Scripts

### 6.1 Historical Acquisition Script

```python
#!/usr/bin/env python3
"""
Historical Data Acquisition Script
Acquires 5-10 years of daily OHLCV data for Nifty 500+ stocks
"""

import yfinance as yf
import pandas as pd
import oracledb
import time
import logging

# Configuration
DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}

SYMBOLS_FILE = '/workspace/quantmudra/nifty500_symbols.csv'
PERIOD = '5y'  # Options: 1y, 2y, 5y, 10y
BATCH_SIZE = 1000

def connect():
    return oracledb.connect(
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        dsn=DB_CONFIG['dsn'],
        config_dir=DB_CONFIG['wallet_location'],
        wallet_location=DB_CONFIG['wallet_location'],
        wallet_password=DB_CONFIG['wallet_password']
    )

def get_last_date(symbol):
    """Get the last stored date for a symbol"""
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(trade_date) 
            FROM admin.stock_ohlcv_daily 
            WHERE symbol = :sym
        """, {'sym': symbol})
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return result
    except:
        return None

def store_data(symbol, nse_symbol, df):
    """Store OHLCV data using MERGE for upsert"""
    if df.empty:
        return 0
    
    conn = connect()
    cursor = conn.cursor()
    stored = 0
    
    for _, row in df.iterrows():
        cursor.execute("""
            MERGE INTO admin.stock_ohlcv_daily t
            USING (SELECT :sym as symbol, :dt as trade_date FROM dual) s
            ON (t.symbol = s.symbol AND t.trade_date = s.trade_date)
            WHEN MATCHED THEN UPDATE SET
                open_price=:open, high_price=:high, low_price=:low,
                close_price=:close, adj_close=:adj, volume=:vol,
                nse_symbol=:nse, updated_at=CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN INSERT 
                (symbol, trade_date, open_price, high_price, low_price,
                 close_price, adj_close, volume, nse_symbol)
            VALUES (:sym,:dt,:open,:high,:low,:close,:adj,:vol,:nse)
        """, {
            'sym': symbol, 'dt': row['Date'].date(),
            'open': float(row['Open']), 'high': float(row['High']),
            'low': float(row['Low']), 'close': float(row['Close']),
            'adj': float(row['Adj Close']), 'vol': int(row['Volume']), 'nse': nse_symbol
        })
        stored += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    return stored

def acquire_historical_data():
    """Main acquisition loop"""
    df_symbols = pd.read_csv(SYMBOLS_FILE)
    symbols = list(zip(df_symbols['yahoo_symbol'], df_symbols['nse_symbol']))
    
    success, failed, total = 0, 0, 0
    
    for i, (yahoo, nse) in enumerate(symbols):
        print(f"[{i+1}/{len(symbols)}] {yahoo}...", end=" ")
        
        try:
            # Check if we already have data
            last_date = get_last_date(yahoo)
            
            # Download data
            data = yf.download(yahoo, period=PERIOD, interval="1d", 
                             auto_adjust=False, progress=False, timeout=15)
            
            if data.empty:
                print("⚠️ No data")
                failed += 1
                continue
            
            # Handle MultiIndex columns
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0] for col in data.columns]
            
            data = data.reset_index()
            data['Date'] = pd.to_datetime(data['Date']).dt.tz_localize(None)
            
            # Store data
            stored = store_data(yahoo, nse, data)
            print(f"✅ {stored:,} records")
            success += 1
            total += stored
            
        except Exception as e:
            print(f"❌ {str(e)[:40]}")
            failed += 1
        
        time.sleep(0.5)  # Rate limit
    
    return {'success': success, 'failed': failed, 'total': total}
```

### 6.2 Daily Incremental Update Script

```python
#!/usr/bin/env python3
"""
Daily Incremental Update Script
Runs via cron at 6:00 PM IST daily
"""

import yfinance as yf
import pandas as pd
import oracledb
from datetime import datetime, timedelta

def is_trading_day(date):
    """Check if date is a trading day"""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM admin.market_holidays 
        WHERE trade_date = :dt AND is_trading_day = 0
    """, {'dt': date})
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count == 0

def connect():
    return oracledb.connect(
        user='admin', password='QuantMudra@2026', dsn='quantmudra_high',
        config_dir='/home/openhands/.oci/quantmudra_wallet',
        wallet_location='/home/openhands/.oci/quantmudra_wallet',
        wallet_password='QuantMudra@2026'
    )

def get_active_symbols():
    """Get list of active symbols to update"""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT symbol FROM admin.stock_ohlcv_daily
        UNION
        SELECT symbol FROM admin.stock_master WHERE is_active = 1
    """)
    symbols = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return symbols

def update_daily():
    """Main daily update function"""
    today = datetime.now().date()
    
    # Skip weekends and holidays
    if not is_trading_day(today):
        print(f"Skipping {today} - Not a trading day")
        return
    
    # Wait until market closes (6:00 PM)
    print(f"Starting daily update for {today}")
    
    symbols = get_active_symbols()
    success, failed = 0, 0
    
    for symbol in symbols:
        try:
            # Get last stored date
            conn = connect()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(trade_date) FROM admin.stock_ohlcv_daily 
                WHERE symbol = :sym
            """, {'sym': symbol})
            last_date = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            if last_date is None:
                continue
            
            # Calculate start date (last date + 1)
            start_date = last_date + timedelta(days=1)
            
            if start_date > today:
                continue  # Already up to date
            
            # Download new data
            data = yf.download(symbol, start=start_date, end=today + timedelta(days=1),
                             interval="1d", progress=False)
            
            if data.empty:
                continue
            
            # Store data (same as historical)
            # ... store_data logic ...
            success += 1
            
        except Exception as e:
            print(f"❌ {symbol}: {str(e)}")
            failed += 1
    
    print(f"Daily update complete: {success} updated, {failed} failed")

if __name__ == "__main__":
    update_daily()
```

---

## 7. Data Quality Framework

### 7.1 Quality Checks

| Check | Description | Severity |
|-------|-------------|----------|
| PRICE_ZERO | Close price is 0 | HIGH |
| HIGH_LOW_INVALID | High < Low | HIGH |
| GAP_CHECK | Large price gap >20% | MEDIUM |
| VOLUME_ZERO | Volume is 0 on trading day | MEDIUM |
| MISSING_DATA | Expected data not found | MEDIUM |
| DUPLICATE_DATE | Multiple records for same date | HIGH |

### 7.2 Data Quality Score Calculation

```sql
SELECT 
    symbol,
    COUNT(*) as total_days,
    SUM(CASE WHEN close_price > 0 THEN 1 ELSE 0 END) as valid_days,
    ROUND(SUM(CASE WHEN close_price > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as quality_score
FROM admin.stock_ohlcv_daily
GROUP BY symbol
ORDER BY quality_score;
```

---

## 8. Scheduled Operations

### 8.1 Cron Schedule

| Time | Task | Command |
|------|------|---------|
| 6:00 AM | Check market status | `check_holiday.py` |
| 6:30 PM | Daily update | `update_daily.py` |
| 7:00 PM | Quality report | `quality_report.py` |
| Sunday 2 AM | Full refresh (if needed) | `acquire_historical.py --full` |

### 8.2 Crontab Entry

```bash
# QuantMudra Data Pipeline
30 18 * * 1-5 cd /workspace/quantmudra && python3 update_daily.py >> /home/openhands/.oci/logs/daily_update.log 2>&1

# Weekly quality check
0 7 * * 0 cd /workspace/quantmudra && python3 quality_report.py >> /home/openhands/.oci/logs/quality.log 2>&1
```

---

## 9. Connection Details

### Oracle ATP Connection
```python
{
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}
```

### Current Statistics
- **Database**: quantmudra_high (Oracle ATP)
- **Records**: 18,717 (as of last check)
- **Stocks**: 15
- **Target**: 620,000+ records (504 stocks × 5 years)

---

## 10. Appendix: Table Creation Scripts

### Stock Master
```sql
CREATE TABLE admin.stock_master (
    symbol VARCHAR2(50) PRIMARY KEY,
    company_name VARCHAR2(200),
    sector VARCHAR2(100),
    industry VARCHAR2(100),
    market_cap_category VARCHAR2(50),
    is_active NUMBER(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Stock OHLCV Daily
```sql
CREATE TABLE admin.stock_ohlcv_daily (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol VARCHAR2(50) NOT NULL,
    trade_date DATE NOT NULL,
    open_price NUMBER(22,4),
    high_price NUMBER(22,4),
    low_price NUMBER(22,4),
    close_price NUMBER(22,4),
    adj_close NUMBER(22,4),
    volume NUMBER(22),
    nse_symbol VARCHAR2(50),
    source VARCHAR2(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_symbol_date UNIQUE (symbol, trade_date)
);

CREATE INDEX idx_ohlcv_trade_date ON admin.stock_ohlcv_daily(trade_date);
CREATE INDEX idx_ohlcv_symbol ON admin.stock_ohlcv_daily(symbol);
```

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-31  
**Author**: QuantMudra Data Engineering Team