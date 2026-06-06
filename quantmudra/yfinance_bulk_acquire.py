"""
QuantMudra - Bulk Data Acquisition from Yahoo Finance
Nifty 500 stocks with 10-year historical data
"""

import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# Setup logging
LOG_DIR = Path("/home/openhands/.oci/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "yfinance_bulk.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BulkDataAcquisition:
    """Bulk acquisition for Nifty 500 stocks."""
    
    def __init__(self, symbols_file: str = None):
        self.symbols_file = symbols_file or '/workspace/quantmudra/nifty500_symbols.csv'
        self.results = []
        
    def load_symbols(self) -> list:
        """Load symbols from CSV file."""
        df = pd.read_csv(self.symbols_file)
        return df['yahoo_symbol'].tolist()
    
    def fetch_stock_data(self, symbol: str, years: int = 10) -> pd.DataFrame:
        """Fetch historical data for a single stock."""
        try:
            df = yf.download(
                symbol,
                period=f"{years}y",
                interval="1d",
                auto_adjust=False,
                progress=False
            )
            
            if df.empty:
                return pd.DataFrame()
            
            # Handle multi-level columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high', 
                'Low': 'low',
                'Close': 'close',
                'Adj Close': 'adj_close',
                'Volume': 'volume'
            })
            
            return df[['Date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']]
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {str(e)}")
            return pd.DataFrame()
    
    def run(self, limit: int = None, years: int = 10, delay: float = 0.3):
        """
        Run bulk acquisition.
        
        Args:
            limit: Max number of symbols to process (None = all)
            years: Years of historical data
            delay: Delay between requests (seconds)
        """
        symbols = self.load_symbols()
        if limit:
            symbols = symbols[:limit]
        
        total = len(symbols)
        logger.info(f"Starting bulk acquisition: {total} symbols")
        print(f"\n{'='*60}")
        print(f"🚀 BULK DATA ACQUISITION - {total} symbols")
        print(f"{'='*60}")
        
        success_count = 0
        failed_count = 0
        
        for i, symbol in enumerate(symbols):
            progress = f"[{i+1}/{total}]"
            print(f"\n{progress} Fetching {symbol}...")
            
            df = self.fetch_stock_data(symbol, years)
            
            if not df.empty:
                success_count += 1
                self.results.append({
                    'symbol': symbol,
                    'status': 'success',
                    'records': len(df),
                    'data': df
                })
                print(f"   ✅ {symbol}: {len(df)} records")
            else:
                failed_count += 1
                self.results.append({
                    'symbol': symbol,
                    'status': 'failed',
                    'records': 0
                })
                print(f"   ❌ {symbol}: No data")
            
            if i < total - 1:
                time.sleep(delay)
        
        print(f"\n{'='*60}")
        print("ACQUISITION COMPLETE")
        print(f"{'='*60}")
        print(f"✅ Success: {success_count}")
        print(f"❌ Failed: {failed_count}")
        
        return self.results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Bulk data acquisition from Yahoo Finance')
    parser.add_argument('--limit', type=int, default=10, help='Number of symbols to process (default: 10)')
    parser.add_argument('--years', type=int, default=10, help='Years of historical data (default: 10)')
    parser.add_argument('--all', action='store_true', help='Process all 500 symbols')
    
    args = parser.parse_args()
    
    acquirer = BulkDataAcquisition()
    
    limit = None if args.all else args.limit
    
    print(f"\n📊 Processing {'ALL' if limit is None else limit} symbols...")
    
    acquirer.run(limit=limit, years=args.years)
    
    # Save results summary
    results_df = pd.DataFrame([{
        'symbol': r['symbol'],
        'status': r['status'],
        'records': r['records']
    } for r in acquirer.results])
    
    results_df.to_csv('/workspace/quantmudra/acquisition_results.csv', index=False)
    print(f"\n📁 Results saved to acquisition_results.csv")
