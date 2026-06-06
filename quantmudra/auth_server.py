#!/usr/bin/env python3
"""
QuantMudra - Auth Code Receiver
Runs a simple HTTP server to capture the auth code from Fyers redirect
"""

import http.server
import urllib.parse
import threading
import sys

PORT = 8080

class AuthHandler(http.server.BaseHTTPRequestHandler):
    auth_code = None
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if 'code' in params:
            AuthHandler.auth_code = params['code'][0]
            print(f"\n✅ AUTH CODE RECEIVED: {AuthHandler.auth_code}\n")
            
            # Save to file
            config_path = "/home/openhands/.oci/fyers_auth_code.txt"
            with open(config_path, 'w') as f:
                f.write(AuthHandler.auth_code)
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body style="font-family:Arial;text-align:center;padding:50px">')
            self.wfile.write(b'<h2 style="color:green">Authorization Complete!</h2>')
            self.wfile.write(b'<p>You can close this window.</p>')
            self.wfile.write(b'</body></html>')
            
            def stop_server():
                import time
                time.sleep(1)
                sys.exit(0)
            threading.Thread(target=stop_server).start()
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'<html><body><h2>No auth code</h2></body></html>')
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    print("=" * 60)
    print("Fyers API Authorization Server")
    print("=" * 60)
    print("\nAuth URL:")
    print("https://api-t1.fyers.in/api/v3/generate-authcode?client_id=IRNM2HYVIF-100&redirect_uri=http%3A%2F%2Flocalhost%3A8080&response_type=code&state=None")
    print("\nWaiting for authorization...")
    
    with socketserver.TCPServer(("", PORT), AuthHandler) as httpd:
        httpd.handle_request()
