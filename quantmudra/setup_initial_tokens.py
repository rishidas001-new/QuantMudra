"""
QuantMudra - Initial Token Setup Script
Run this once to set up the Fyers API tokens
"""

import sys
sys.path.insert(0, '/workspace/quantmudra')

from fyers_config import FyersTokenManager, DB_CONFIG

def setup_initial_tokens():
    """
    Setup initial tokens from Fyers API.
    This requires a one-time authorization code.
    """
    print("=" * 60)
    print("QuantMudra - Fyers API Initial Token Setup")
    print("=" * 60)
    
    token_manager = FyersTokenManager(DB_CONFIG)
    
    # Check if tokens already exist
    if token_manager.load_tokens():
        if token_manager.is_token_valid():
            print("\n✅ Tokens already exist and are valid!")
            print(f"   Token: {token_manager.access_token[:20]}...")
            print(f"   Expires: {token_manager.token_expiry}")
            return True
        else:
            print("\n⚠️  Tokens exist but are expired. Attempting refresh...")
            result = token_manager.refresh_access_token()
            if result.get('s') == 'ok':
                print("✅ Token refreshed successfully!")
                return True
    
    print("\n📝 First-time Setup Required")
    print("-" * 40)
    print("""
To obtain tokens, you need to:

1. Build the authorization URL:
   https://www.fyers.in/api/v2/generate-authcode/?client_id=IRNM2HYVIF-100&redirect_uri=https://api.fyers.in&response_type=code&state=default

2. Visit the URL in a browser and authorize the app

3. You will be redirected to:
   https://api.fyers.in?code=AUTH_CODE_HERE

4. Copy the AUTH_CODE from the URL

5. Paste the code below when prompted
    """)
    
    auth_code = input("\nEnter the authorization code: ").strip()
    
    if not auth_code:
        print("❌ No authorization code provided")
        return False
    
    print("\nGenerating tokens from authorization code...")
    result = token_manager.generate_access_token(auth_code)
    
    if result.get('s') == 'ok':
        print("\n✅ Tokens generated successfully!")
        
        # Save tokens to database
        token_manager.save_tokens(
            result['access_token'],
            result.get('refresh_token', ''),
            result.get('expires_in', 86400)
        )
        
        print(f"   Access Token: {result['access_token'][:20]}...")
        print(f"   Refresh Token: {result.get('refresh_token', 'N/A')[:20]}...")
        print(f"   Expires in: {result.get('expires_in', 'N/A')} seconds")
        
        return True
    else:
        print(f"\n❌ Token generation failed: {result}")
        return False

if __name__ == "__main__":
    success = setup_initial_tokens()
    sys.exit(0 if success else 1)
