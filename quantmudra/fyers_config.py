"""
QuantMudra - Fyers API Configuration Module
Handles OAuth2 token management with automatic refresh
"""

import os
import json
import requests
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict

# Configuration
APP_ID = "IRNM2HYVIF-100"
SECRET_ID = "CZDV2C7RU5"
TOKEN_URL = "https://api.fyers.in/api/v2/token"

class FyersTokenManager:
    """
    Manages Fyers API tokens with automatic refresh.
    Stores tokens in Oracle database for persistence.
    """
    
    def __init__(self, db_config: dict):
        self.app_id = APP_ID
        self.secret_id = SECRET_ID
        self.db_config = db_config
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        
    def _get_db_connection(self):
        """Create database connection using oracledb"""
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
    
    def save_tokens(self, access_token: str, refresh_token: str, expires_in: int):
        """Save tokens to database"""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        expiry_time = datetime.now() + timedelta(seconds=expires_in - 300)  # 5 min buffer
        
        cursor.execute("""
            MERGE INTO admin.fyers_api_config t
            USING (SELECT :key as config_key FROM dual) s
            ON (t.config_key = s.config_key)
            WHEN MATCHED THEN
                UPDATE SET config_value = :value, created_at = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (config_key, config_value, description, is_encrypted)
                VALUES (:key, :value, :desc, 0)
        """, {"key": "access_token", "value": access_token, "desc": "Fyers API access token"})
        
        cursor.execute("""
            MERGE INTO admin.fyers_api_config t
            USING (SELECT :key as config_key FROM dual) s
            ON (t.config_key = s.config_key)
            WHEN MATCHED THEN
                UPDATE SET config_value = :value, created_at = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (config_key, config_value, description, is_encrypted)
                VALUES (:key, :value, :desc, 0)
        """, {"key": "refresh_token", "value": refresh_token, "desc": "Fyers API refresh token"})
        
        cursor.execute("""
            MERGE INTO admin.fyers_api_config t
            USING (SELECT :key as config_key FROM dual) s
            ON (t.config_key = s.config_key)
            WHEN MATCHED THEN
                UPDATE SET config_value = :value, created_at = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (config_key, config_value, description, is_encrypted)
                VALUES (:key, :value, :desc, 0)
        """, {"key": "token_expiry", "value": expiry_time.isoformat(), "desc": "Token expiry timestamp"})
        
        conn.commit()
        cursor.close()
        conn.close()
        
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = expiry_time
    
    def load_tokens(self) -> bool:
        """Load tokens from database. Returns True if valid tokens exist."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT config_key, config_value 
                FROM admin.fyers_api_config 
                WHERE config_key IN ('access_token', 'refresh_token', 'token_expiry')
            """)
            
            tokens = {}
            for row in cursor.fetchall():
                tokens[row[0]] = row[1]
            
            cursor.close()
            conn.close()
            
            if 'access_token' in tokens and 'refresh_token' in tokens:
                self.access_token = tokens['access_token']
                self.refresh_token = tokens['refresh_token']
                if 'token_expiry' in tokens:
                    self.token_expiry = datetime.fromisoformat(tokens['token_expiry'])
                return True
            
            return False
            
        except Exception as e:
            print(f"Error loading tokens: {e}")
            return False
    
    def is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.now() < self.token_expiry
    
    def generate_access_token(self, auth_code: str) -> Dict:
        """Generate access token from auth code (one-time setup)"""
        data = {
            "grant_type": "authorization_code",
            "appId": self.app_id,
            "secretId": self.secret_id,
            "redirect_uri": "https://api.fyers.in",
            "code": auth_code
        }
        
        response = requests.post(TOKEN_URL, data=data)
        return response.json()
    
    def refresh_access_token(self) -> Dict:
        """Refresh the access token using refresh token"""
        data = {
            "grant_type": "refresh_token",
            "appId": self.app_id,
            "secretId": self.secret_id,
            "refresh_token": self.refresh_token
        }
        
        response = requests.post(TOKEN_URL, data=data)
        result = response.json()
        
        if result.get('s') == 'ok':
            # Save new tokens
            self.save_tokens(
                result['access_token'],
                result.get('refresh_token', self.refresh_token),
                result.get('expires_in', 86400)
            )
        
        return result
    
    def get_valid_token(self) -> str:
        """
        Main method to get a valid access token.
        Automatically refreshes if expired.
        """
        if self.is_token_valid():
            return self.access_token
        
        # Try to load from database
        if self.load_tokens():
            if self.is_token_valid():
                return self.access_token
        
        # Token expired, refresh it
        if self.refresh_token:
            result = self.refresh_access_token()
            if result.get('s') == 'ok':
                return self.access_token
        
        raise Exception("Cannot obtain valid token. Manual authorization required.")


# Database configuration
DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026!',
    'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026!'
}

# Initialize singleton
token_manager = FyersTokenManager(DB_CONFIG)
