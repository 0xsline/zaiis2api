import services
from app import app
from models import Token
import tls_client
import json

def debug_request_tls():
    with app.app_context():
        token_entry = Token.query.get(11)
        if not token_entry:
            print("Token 11 not found")
            return

        print(f"Using Discord Token: {token_entry.discord_token[:10]}...")
        
        # 1. Login to get Cookies (using services helper which uses requests)
        handler = services.get_zai_handler()
        result = handler.backend_login(token_entry.discord_token)
        
        if 'error' in result:
            print(f"Login failed: {result['error']}")
            return

        jwt_token = result.get('token')
        cookies = handler.session.cookies.get_dict()
        print(f"Captured Cookies: {cookies.keys()}")
        
        # 2. Use tls_client with captured cookies
        session = tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )
        
        url = "https://zai.is/api/v1/models"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://zai.is",
            "Referer": "https://zai.is/chat",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": '"Chromium";v="120", "Google Chrome";v="120", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"'
        }
        
        print("\nSending TLS request with cookies...")
        try:
            # tls_client expects cookies as dict
            resp = session.get(url, headers=headers, cookies=cookies, timeout_seconds=10)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    debug_request_tls()
