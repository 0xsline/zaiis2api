import services
from extensions import db
from app import app
from models import Token
import requests
import json

def debug_request():
    with app.app_context():
        # Get Token 11's discord token
        token_entry = Token.query.get(11)
        if not token_entry:
            print("Token 11 not found")
            return

        print(f"Using Discord Token: {token_entry.discord_token[:10]}...")
        
        # Use existing handler to login and get cookies
        handler = services.get_zai_handler()
        result = handler.backend_login(token_entry.discord_token)
        
        if 'error' in result:
            print(f"Login failed: {result['error']}")
            return

        jwt_token = result.get('token')
        print(f"Got JWT: {jwt_token[:10]}...")
        
        # Extract cookies from the session
        cookies = handler.session.cookies.get_dict()
        print(f"Captured Cookies: {cookies}")
        
        # Now try to hit the API using these cookies and the JWT
        url = "https://zai.is/api/v1/models"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://zai.is",
            "Referer": "https://zai.is/"
        }
        
        print("\nSending request with cookies...")
        try:
            # Use requests first to see if cookies help standard requests
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    debug_request()
