"""
QuantMudra - Yahoo Finance to Oracle ATP Data Pipeline
Bulk data acquisition and storage for Nifty 500 stocks
"""

import sys
import time
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import yfinance as yf
import oracledb

# Setup logging
LOG_DIR = Path("/home/openhands/.oci/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "yfinance_to_oracle.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database Configuration
DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}


class OracleDataWriter:
    """Writes data to Oracle ATP"""
    
    def __init__(self, db_config):
        self.db_config = db_config
        
    def get_connection(self):
        return oracledb.connect(
            user=self.db_config['user'],
            password=self.db_config['password'],
            dsn=self.db_config['dsn'],
            config_dir=self.db_config['wallet_location'],
            wallet_location=self.db_config['wallet_location'],
            wallet_password=self.db_config['wallet_password']
        )
    
    def store_ohlcv(self, symbol: str, nse_symbol: str, df: pd.DataFrame) -> int:
        """Store OHLCV data to Oracle ATP"""
        if df.empty:
            return 0
            
        conn = self.get_connection()
        cursor = conn.cursor()
        stored = 0
        
        try:
            for _, row in df.iterrows():
                cursor.execute("""
                    MERGE INTO admin.stock_ohlcv_daily t
                    USING (SELECT :symbol as symbol, :trade_date as trade_date FROM dual) s
                    ON (t.symbol = s.symbol AND t.trade_date = s.trade_date)
                    WHEN MATCHED THEN UPDATE SET
                        open_price = :open,
                        high_price = :high,
                        low_price = :low,
                        close_price = :close,
                        adj_close = :adj_close,
                        volume = :volume,
                        nse_symbol = :nse_symbol,
                        updated_at = CURRENT_TIMESTAMP
                    WHEN NOT MATCHED THEN INSERT 
                        (symbol, trade_date, open_price, high_price, low_price, close_price, adj_close, volume, nse_symbol)
                    VALUES (:symbol, :trade_date, :open, :high, :low, :close, :adj_close, :volume, :nse_symbol)
                """, {
                    'symbol': symbol,
                    'trade_date': row['Date'].date() if hasattr(row['Date'], 'date') else row['Date'],
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'adj_close': row['adj_close'],
                    'volume': int(row['volume']),
                    'nse_symbol': nse_symbol
                })
                stored += 1
                
            conn.commit()
            logger.info(f"Stored {stored} records for {symbol}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing {symbol}: {str(e)}")
        finally:
            cursor.close()
            conn.close()
            
        return stored
    
    def log_refresh(self, symbol: str, status: str, records: int, error: str = None):
        """Log refresh operation"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO admin.data_refresh_log 
                (symbol, data_type, start_date, end_date, record_count, status, error_message)
                VALUES (:symbol, 'YFINANCE', SYSDATE-3650, SYSDATE, :count, :status, :error)
            """, {'symbol': symbol, 'count': records, 'status': status, 'error': error})
            conn.commit()
        except:
            pass
        finally:
            cursor.close()
            conn.close()


class YahooFinanceFetcher:
    """Fetches data from Yahoo Finance"""
    
    def __init__(self, writer: OracleDataWriter):
        self.writer = writer
        self.rate_limit_delay = 0.3
        
    def _convert_symbol(self, symbol: str) -> str:
        """Convert NSE format to Yahoo format"""
        if symbol.startswith("NSE:"):
            symbol = symbol.replace("NSE:", "").replace("-EQ", "")
        if not symbol.endswith(".NS"):
            symbol = symbol + ".NS"
        return symbol
    
    def fetch_and_store(self, symbol: str, years: int = 10) -> tuple:
        """Fetch data and store to Oracle"""
        yahoo_symbol = self._convert_symbol(symbol)
        nse_symbol = symbol if symbol.startswith("NSE:") else f"NSE:{symbol}-EQ"
        
        logger.info(f"Fetching {yahoo_symbol}...")
        
        try:
            df = yf.download(
                yahoo_symbol,
                period=f"{years}y",
                interval="1d",
                auto_adjust=False,
                progress=False
            )
            
            if df.empty:
                self.writer.log_refresh(symbol, 'NO_DATA', 0)
                return 0, False
            
            # Handle multi-level columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            
            df = df.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Adj Close': 'adj_close', 'Volume': 'volume'
            })
            
            stored = self.writer.store_ohlcv(symbol, nse_symbol, df)
            self.writer.log_refresh(symbol, 'SUCCESS', stored)
            
            return len(df), True
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {str(e)}")
            self.writer.log_refresh(symbol, 'ERROR', 0, str(e))
            return 0, False


class BulkAcquisitionPipeline:
    """Main pipeline for bulk acquisition"""
    
    def __init__(self):
        self.writer = OracleDataWriter(DB_CONFIG)
        self.fetcher = YahooFinanceFetcher(self.writer)
        self.results = []
        
    def load_symbols(self, limit: int = None) -> list:
        """Load symbols from CSV"""
        df = pd.read_csv('/workspace/quantmudra/nifty500_symbols.csv')
        symbols = df['yahoo_symbol'].tolist()
        if limit:
            symbols = symbols[:limit]
        return symbols
    
    def run(self, limit: int = None, years: int = 10, delay: float = 0.3):
        """Run bulk acquisition"""
        symbols = self.load_symbols(limit)
        total = len(symbols)
        
        logger.info(f"Starting bulk acquisition: {total} symbols")
        print(f"\n{'='*60}")
        print(f"🚀 BULK DATA ACQUISITION - {total} symbols")
        print(f"{'='*60}")
        
        success = 0
        failed = 0
        total_records = 0
        
        for i, symbol in enumerate(symbols):
            progress = f"[{i+1}/{total}]"
            print(f"\n{progress} Processing {symbol}...")
            
            count, ok = self.fetcher.fetch_and_store(symbol, years)
            
            if ok:
                success += 1
                total_records += count
                print(f"   ✅ {symbol}: {count} records stored")
            else:
                failed += 1
                print(f"   ❌ {symbol}: Failed")
            
            if i < total - 1:
                time.sleep(delay)
        
        print(f"\n{'='*60}")
        print("ACQUISITION COMPLETE")
        print(f"{'='*60}")
        print(f"✅ Success: {success}/{total}")
        print(f"❌ Failed: {failed}/{total}")
        print(f"📊 Total Records: {total_records:,}")
        
        logger.info(f"Complete: {success} success, {failed} failed, {total_records} records")
        return {'success': success, 'failed': failed, 'records': total_records}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20, help='Number of symbols')
    parser.add_argument('--years', type=int, default=10, help='Years of data')
    args = parser.parse_args()
    
    pipeline = BulkAcquisitionPipeline()
    pipeline.run(limit=args.limit, years=args.years)
