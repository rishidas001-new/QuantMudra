"""
QuantMudra - Token Refresh Service
Automatically refreshes Fyers API tokens
Can be run as cron job or systemd service
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
LOG_DIR = Path("/home/openhands/.oci/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "token_refresh.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def refresh_token():
    """Main function to refresh the token"""
    try:
        sys.path.insert(0, '/workspace/quantmudra')
        from fyers_config import FyersTokenManager, DB_CONFIG
        
        logging.info("Starting token refresh...")
        
        token_manager = FyersTokenManager(DB_CONFIG)
        
        # Try to load existing tokens
        if token_manager.load_tokens():
            logging.info("Found existing tokens in database")
            
            # Check if token is valid
            if token_manager.is_token_valid():
                logging.info("Token is still valid, no refresh needed")
                print("Token is valid, no refresh needed")
                return True
            
            # Token expired, refresh it
            logging.info("Token expired, refreshing...")
            result = token_manager.refresh_access_token()
            
            if result.get('s') == 'ok':
                logging.info("Token refreshed successfully")
                print("✅ Token refreshed successfully")
                print(f"   New token: {result['access_token'][:20]}...")
                return True
            else:
                logging.error(f"Token refresh failed: {result}")
                print(f"❌ Token refresh failed: {result}")
                return False
        else:
            logging.warning("No tokens found in database")
            print("⚠️  No tokens found in database")
            print("   Manual authorization required")
            return False
            
    except Exception as e:
        logging.error(f"Token refresh error: {e}")
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = refresh_token()
    sys.exit(0 if success else 1)
