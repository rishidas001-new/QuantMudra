"""
QuantMudra - Fyers API v3 Authentication Module
"""

import sys
import json
import logging
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path("/home/openhands/.oci/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=str(LOG_DIR / "fyers_auth.log"), level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# NEW Fyers API Configuration
APP_ID = "KH668RLT43-100"
SECRET_ID = "K0CAP3659A"
REDIRECT_URI = "http://127.0.0.1"
TOKEN_URL = "https://api.fyers.in/api/v3/token"

DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026!',
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026!'
}

def generate_app_id_hash(client_id: str, secret_key: str) -> str:
    combined = f"{client_id}{secret_key}"
    return hashlib.sha256(combined.encode()).hexdigest()

class FyersAuth:
    def __init__(self, db_config: dict):
        self.app_id = APP_ID
        self.secret_id = SECRET_ID
        self.redirect_uri = REDIRECT_URI
        self.db_config = db_config
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        from fyers_apiv3 import fyersModel
        self.SessionModel = fyersModel.SessionModel
        
    def _get_db_connection(self):
        import oracledb
        wallet_dir = self.db_config['wallet_location']
        return oracledb.connect(
            user=self.db_config['user'], password=self.db_config['password'],
            dsn=self.db_config['dsn'], config_dir=wallet_dir,
            wallet_location=wallet_dir, wallet_password=self.db_config['wallet_password']
        )
    
    def save_tokens(self, access_token: str, refresh_token: str = None, expires_in: int = 86400):
        conn = self._get_db_connection()
        cursor = conn.cursor()
        expiry = datetime.now() + timedelta(seconds=expires_in - 300)
        
        for key, value, desc in [
            ('access_token', access_token, 'Fyers API access token'),
            ('refresh_token', refresh_token or '', 'Fyers API refresh token'),
            ('token_expiry', expiry.isoformat(), 'Token expiry timestamp')
        ]:
            cursor.execute("""
                MERGE INTO admin.fyers_api_config t
                USING (SELECT :key as config_key FROM dual) s
                ON (t.config_key = s.config_key)
                WHEN MATCHED THEN UPDATE SET config_value = :value, created_at = CURRENT_TIMESTAMP
                WHEN NOT MATCHED THEN INSERT (config_key, config_value, description, is_encrypted)
                VALUES (:key, :value, :desc, 0)
            """, {'key': key, 'value': value, 'desc': desc})
        
        conn.commit()
        cursor.close()
        conn.close()
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = expiry
        logging.info("Tokens saved to database")
    
    def load_tokens(self) -> bool:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""SELECT config_key, config_value FROM admin.fyers_api_config 
                            WHERE config_key IN ('access_token', 'refresh_token', 'token_expiry')""")
            tokens = {}
            for row in cursor.fetchall():
                tokens[row[0]] = row[1]
            cursor.close()
            conn.close()
            
            if 'access_token' in tokens:
                self.access_token = tokens['access_token']
                self.refresh_token = tokens.get('refresh_token', '')
                if 'token_expiry' in tokens:
                    self.token_expiry = datetime.fromisoformat(tokens['token_expiry'])
                return True
            return False
        except Exception as e:
            logging.error(f"Error loading tokens: {e}")
            return False
    
    def is_token_valid(self) -> bool:
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.now() < self.token_expiry
    
    def generate_auth_url(self) -> str:
        session = self.SessionModel(client_id=self.app_id, secret_key=self.secret_id,
                                   redirect_uri=self.redirect_uri, response_type='code', state='None')
        return session.generate_authcode()
    
    def get_token_from_auth_code(self, auth_code: str) -> dict:
        session = self.SessionModel(client_id=self.app_id, secret_key=self.secret_id,
                                   redirect_uri=self.redirect_uri, response_type='code', state='None')
        session.set_token(auth_code)
        return session.generate_token()
    
    def refresh_access_token(self, pin: str = "1234") -> dict:
        if not self.refresh_token:
            return {'s': 'error', 'message': 'No refresh token available'}
        
        app_id_hash = generate_app_id_hash(self.app_id, self.secret_id)
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {"grant_type": "refresh_token", "appIdHash": app_id_hash,
                "refresh_token": self.refresh_token, "pin": pin}
        
        response = requests.post(TOKEN_URL, headers=headers, json=data)
        result = response.json()
        
        if result.get('s') == 'ok':
            self.save_tokens(result['access_token'], result.get('refresh_token'), result.get('expires_in', 86400))
        return result
    
    def get_valid_token(self) -> str:
        if self.is_token_valid():
            return self.access_token
        if self.load_tokens():
            if self.is_token_valid():
                return self.access_token
        if self.refresh_token:
            result = self.refresh_access_token()
            if result.get('s') == 'ok':
                return self.access_token
        raise Exception("Cannot obtain valid token. Manual authorization required.")


def initial_setup(auth_code: str = None):
    auth = FyersAuth(DB_CONFIG)
    
    if not auth_code:
        url = auth.generate_auth_url()
        print("\n" + "=" * 60)
        print("📝 First-Time Authorization Required (API v3)")
        print("=" * 60)
        print(f"\n🔗 Auth URL:\n{url}")
        print(f"\n1. Open the URL above in your browser")
        print("2. Log in and authorize the app")
        print("3. You'll be redirected to http://127.0.0.1/?code=XXXXX")
        print("4. Copy the CODE from the URL and provide it here")
        return None
    
    print("Exchanging authorization code for tokens...")
    response = auth.get_token_from_auth_code(auth_code)
    
    if response.get('s') == 'ok':
        auth.save_tokens(response['access_token'], response.get('refresh_token'), response.get('expires_in', 86400))
        print("\n✅ Tokens saved successfully!")
        print(f"   Access Token: {response['access_token'][:20]}...")
        return True
    else:
        print(f"\n❌ Failed: {response}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Fyers API v3 Token Management')
    parser.add_argument('--auth-code', help='Authorization code for initial setup')
    parser.add_argument('--setup', action='store_true', help='Show auth URL')
    args = parser.parse_args()
    
    if args.setup:
        initial_setup()
    elif args.auth_code:
        initial_setup(args.auth_code)
    else:
        auth = FyersAuth(DB_CONFIG)
        try:
            token = auth.get_valid_token()
            print(f"✅ Token available: {token[:20]}...")
        except Exception as e:
            print(f"❌ Token error: {e}")
            print("\nRun with --setup for first-time authorization")
