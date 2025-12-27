import requests
import services
from app import app
from models import Token
import json
import time

def manual_init():
    with app.app_context():
        token_entry = Token.query.get(11)
        if not token_entry:
            print("Token 11 not found")
            return
            
        print(f"Logging in with Token 11...")
        handler = services.get_zai_handler()
        result = handler.backend_login(token_entry.discord_token)
        
        if 'error' in result:
            print(f"Login failed: {result['error']}")
            return
            
        cookies = handler.session.cookies.get_dict()
        print(f"Got cookies: {list(cookies.keys())}")
        
        # Call browser service locally (mapped port 5005)
        try:
            resp = requests.post("http://localhost:5005/init", json={'cookies': cookies})
            print(f"Init response: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Failed to call browser service: {e}")

        # Check if header is available
        print("Checking header availability...")
        for i in range(15):
            try:
                resp = requests.get("http://localhost:5005/header")
                if resp.status_code == 200:
                    data = resp.json()
                    if 'header' in data:
                        print(f"\n[SUCCESS] Header available: {data['header'][:30]}...")
                        return
                    else:
                        print(f"Service returned 200 but no header: {data}")
                else:
                    print(f"Waiting for header... {resp.status_code} {resp.text.strip()}")
            except Exception as e:
                print(f"Waiting for service... ({e})")
            time.sleep(2)

if __name__ == "__main__":
    manual_init()