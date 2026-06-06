"""
QuantMudra - Yahoo Finance Data Acquisition Engine
Day-level OHLCV data for Nifty 500 stocks with 10-year history
"""

import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from pathlib import Path

import pandas as pd
import yfinance as yf

# Setup logging
LOG_DIR = Path("/home/openhands/.oci/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "yfinance_acquisition.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YahooFinanceDataFetcher:
    """Fetches historical OHLCV data from Yahoo Finance."""
    
    def __init__(self):
        self.rate_limit_delay = 0.3
        
    def _convert_symbol(self, symbol: str) -> str:
        """Convert from NSE format to Yahoo format"""
        if symbol.startswith("NSE:"):
            symbol = symbol.replace("NSE:", "").replace("-EQ", "")
        if not symbol.endswith(".NS"):
            symbol = symbol + ".NS"
        return symbol
    
    def fetch_historical_data(self, symbol: str, years: int = 10) -> pd.DataFrame:
        """Fetch historical OHLCV data from Yahoo Finance."""
        yahoo_symbol = self._convert_symbol(symbol)
        logger.info(f"Fetching {years} years of data for {yahoo_symbol}")
        
        try:
            df = yf.download(
                yahoo_symbol,
                period=f"{years}y",
                interval="1d",
                auto_adjust=False,
                progress=False
            )
            
            if df.empty:
                logger.warning(f"No data returned for {yahoo_symbol}")
                return pd.DataFrame()
            
            # Handle multi-level columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            
            # Flatten index
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            
            # Rename columns
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high', 
                'Low': 'low',
                'Close': 'close',
                'Adj Close': 'adj_close',
                'Volume': 'volume'
            })
            
            # Keep only needed columns
            df = df[['Date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']].copy()
            df['symbol'] = symbol
            
            logger.info(f"Fetched {len(df)} records for {yahoo_symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {str(e)}")
            return pd.DataFrame()
    
    def get_corporate_actions(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """Fetch corporate actions (splits and dividends) for a symbol."""
        yahoo_symbol = self._convert_symbol(symbol)
        
        try:
            ticker = yf.Ticker(yahoo_symbol)
            
            splits = ticker.splits
            dividends = ticker.dividends
            
            splits_df = pd.DataFrame()
            dividends_df = pd.DataFrame()
            
            if len(splits) > 0:
                splits_df = pd.DataFrame({
                    'date': pd.to_datetime(splits.index).tz_localize(None),
                    'split_ratio': splits.values
                })
                
            if len(dividends) > 0:
                dividends_df = pd.DataFrame({
                    'date': pd.to_datetime(dividends.index).tz_localize(None),
                    'dividend': dividends.values
                })
                
            return {'splits': splits_df, 'dividends': dividends_df}
            
        except Exception as e:
            logger.error(f"Error fetching corporate actions for {symbol}: {str(e)}")
            return {'splits': pd.DataFrame(), 'dividends': pd.DataFrame()}


class DataAcquisitionEngine:
    """Orchestrates data acquisition from Yahoo Finance."""
    
    def __init__(self):
        self.fetcher = YahooFinanceDataFetcher()
        
    def acquire_stock_data(self, symbol: str, years: int = 10) -> Tuple[pd.DataFrame, bool]:
        """Acquire historical data for a single stock."""
        logger.info(f"Acquiring data for {symbol}")
        
        try:
            df = self.fetcher.fetch_historical_data(symbol, years)
            
            if df.empty:
                return pd.DataFrame(), False
                
            return df, True
            
        except Exception as e:
            logger.error(f"Error acquiring {symbol}: {str(e)}")
            return pd.DataFrame(), False
    
    def bulk_acquire(self, symbols: List[str], years: int = 10, delay: float = 0.3) -> Dict:
        """Acquire data for multiple symbols with rate limiting."""
        logger.info(f"Starting bulk acquisition for {len(symbols)} symbols")
        
        results = {}
        for i, symbol in enumerate(symbols):
            logger.info(f"Processing {i+1}/{len(symbols)}: {symbol}")
            
            df, success = self.acquire_stock_data(symbol, years)
            results[symbol] = {'success': success, 'records': len(df), 'data': df}
            
            if i < len(symbols) - 1:
                time.sleep(delay)
        
        logger.info(f"Bulk acquisition complete")
        return results


# Sample Nifty 50 symbols
SAMPLE_SYMBOLS = [
    "NSE:RELIANCE-EQ", "NSE:TCS-EQ", "NSE:HDFCBANK-EQ", "NSE:INFOSYS-EQ",
    "NSE:ICICIBANK-EQ", "NSE:HINDUSTANLIM-EQ", "NSE:SBIN-EQ", "NSE:BHARTIARTL-EQ",
    "NSE:LarsenToubro-EQ", "NSE:ITC-EQ"
]


if __name__ == "__main__":
    print("="*60)
    print("QuantMudra - Yahoo Finance Data Acquisition")
    print("="*60)
    
    engine = DataAcquisitionEngine()
    
    print("\n📊 Testing single stock acquisition...")
    df, success = engine.acquire_stock_data("NSE:RELIANCE-EQ", years=10)
    
    if success and not df.empty:
        print(f"\n✅ Successfully fetched {len(df)} records")
        print(f"\nSample data (last 5 days):")
        print(df[['Date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']].tail())
        
        # Check corporate actions
        corp = engine.fetcher.get_corporate_actions("NSE:RELIANCE-EQ")
        if not corp['splits'].empty:
            print(f"\n📈 Recent splits:")
            print(corp['splits'].tail())
        if not corp['dividends'].empty:
            print(f"\n💰 Recent dividends:")
            print(corp['dividends'].tail())
    else:
        print(f"\n❌ Acquisition failed")
