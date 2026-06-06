"""
QuantMudra - Data Acquisition Engine
Fyers API Integration for Nifty 500 stocks with 10-year historical data
"""

import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class FyersDataFetcher:
    """
    Fetches historical OHLCV data from Fyers API.
    Handles token management automatically.
    """
    
    BASE_URL = "https://api.fyers.in"
    
    def __init__(self, token_manager):
        self.token_manager = token_manager
        
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated API request"""
        token = self.token_manager.get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=headers, params=params)
        
        result = response.json()
        
        if result.get('s') == 'error':
            raise Exception(f"API Error: {result.get('message', 'Unknown error')}")
            
        return result
    
    def get_historical_data(self, symbol: str, from_date: str, to_date: str, 
                           interval: str = "1D") -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a symbol.
        
        Args:
            symbol: Fyers symbol (e.g., "NSE:RELIANCE-EQ")
            from_date: Start date (format: "%Y-%m-%d")
            to_date: End date (format: "%Y-%m-%d")
            interval: Data interval ("1D", "1H", "5min", etc.)
            
        Returns:
            DataFrame with OHLCV data
        """
        params = {
            "symbol": symbol,
            "resolution": interval,
            "date_format": "1",
            "range_from": from_date,
            "range_to": to_date
        }
        
        result = self._make_request("/data/v2/historical", params)
        
        if result.get('s') == 'ok' and 'candles' in result:
            df = pd.DataFrame(result['candles'], 
                            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='s')
            df.drop('timestamp', axis=1, inplace=True)
            return df
        
        return pd.DataFrame()
    
    def get_nifty500_symbols(self) -> List[str]:
        """
        Get list of Nifty 500 stock symbols.
        Uses Fyers symbol format.
        """
        # Nifty 500 is a subset - we'll use a predefined list
        # In production, this should be fetched from NSE/BSE API
        return [
            "NSE:RELIANCE-EQ", "NSE:TCS-EQ", "NSE:HDFCBANK-EQ", "NSE:INFOSYS-EQ",
            "NSE:ICICIBANK-EQ", "NSE:HINDUSTANLIM-EQ", "NSE:SBIN-EQ", "NSE:BHARTIARTL-EQ",
            "NSE:LarsenToubro-EQ", "NSE:ITC-EQ"
            # Add remaining symbols...
        ]


class DataAcquisitionEngine:
    """
    Orchestrates data acquisition from Fyers API.
    Manages bulk downloads with rate limiting and error handling.
    """
    
    def __init__(self, db_config: dict):
        from fyers_config import FyersTokenManager, DB_CONFIG
        self.token_manager = FyersTokenManager(db_config)
        self.fetcher = FyersDataFetcher(self.token_manager)
        self.db_config = db_config
        
    def _get_db_connection(self):
        import oracledb
        wallet_dir = self.db_config['wallet_location']
        return oracledb.connect(
            user=self.db_config['user'],
            password=self.db_config['password'],
            dsn=self.db_config['dsn'],
            config_dir=wallet_dir,
            wallet_location=wallet_dir,
            wallet_password=self.db_config['wallet_password']
        )
    
    def log_refresh(self, symbol: str, status: str, record_count: int = 0, 
                   error: str = None):
        """Log data refresh operation"""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO admin.data_refresh_log 
            (symbol, data_type, start_date, end_date, record_count, status, error_message)
            VALUES (:symbol, 'HISTORICAL', TO_DATE(:start_date, 'YYYY-MM-DD'), 
                    TO_DATE(:end_date, 'YYYY-MM-DD'), :count, :status, :error)
        """, {
            'symbol': symbol,
            'start_date': '2014-01-01',
            'end_date': datetime.now().strftime('%Y-%m-%d'),
            'count': record_count,
            'status': status,
            'error': error
        })
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def acquire_stock_data(self, symbol: str, years: int = 10) -> bool:
        """
        Acquire historical data for a single stock.
        """
        try:
            from_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            
            df = self.fetcher.get_historical_data(symbol, from_date, to_date)
            
            if not df.empty:
                self.log_refresh(symbol, 'SUCCESS', len(df))
                print(f"  ✅ {symbol}: {len(df)} records")
                return True
            else:
                self.log_refresh(symbol, 'NO_DATA')
                print(f"  ⚠️  {symbol}: No data returned")
                return False
                
        except Exception as e:
            self.log_refresh(symbol, 'ERROR', error=str(e))
            print(f"  ❌ {symbol}: {str(e)[:50]}")
            return False
    
    def bulk_acquire(self, symbols: List[str], delay: float = 0.5):
        """
        Acquire data for multiple symbols with rate limiting.
        """
        print(f"\nStarting bulk acquisition for {len(symbols)} symbols...")
        success = 0
        failed = 0
        
        for symbol in symbols:
            if self.acquire_stock_data(symbol):
                success += 1
            else:
                failed += 1
            time.sleep(delay)  # Rate limiting
        
        print(f"\nBulk acquisition complete:")
        print(f"  ✅ Success: {success}")
        print(f"  ❌ Failed: {failed}")
        
        return {'success': success, 'failed': failed}


# Standalone execution
if __name__ == "__main__":
    from fyers_config import DB_CONFIG
    
    engine = DataAcquisitionEngine(DB_CONFIG)
    
    # Test connection
    print("Testing Fyers API connection...")
    try:
        token = engine.token_manager.get_valid_token()
        print(f"✅ Token obtained: {token[:20]}...")
    except Exception as e:
        print(f"❌ Token error: {e}")
        print("\n📝 First-time setup required:")
        print("   1. Generate auth code from Fyers API")
        print("   2. Use token_manager.generate_access_token(auth_code)")
