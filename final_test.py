import requests
import time

def run_test():
    print("Checking Browser Service status...")
    try:
        resp = requests.get("http://localhost:5005/status", timeout=5)
        print(f"Status: {resp.json()}")
    except Exception as e:
        print(f"Browser Service not reachable: {e}")
        return

    print("\nTriggering Manual Init...")
    import services
    from app import app
    from models import Token
    with app.app_context():
        token_entry = Token.query.get(11)
        handler = services.get_zai_handler()
        result = handler.backend_login(token_entry.discord_token)
        cookies = handler.session.cookies.get_dict()
        requests.post("http://localhost:5005/init", json={'cookies': cookies})

    # DIRECTLY Request Header with long timeout
    print("\nRequesting Header from Browser Service (this will launch browser)...")
    dk_header = None
    try:
        # Give it plenty of time to launch browser and navigate
        resp = requests.get("http://localhost:5005/header", timeout=90)
        if resp.status_code == 200:
            dk_header = resp.json().get('header')
            print(f"[SUCCESS] Header captured: {dk_header[:30]}...")
        else:
            print(f"[FAILED] Browser Service returned {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        print(f"Request to /header failed: {e}")
        return

    # 4. Final Chat Request
    print("\nSending Chat Request to API Service (localhost:5002)...")
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Tell me a short joke."}],
        "stream": False
    }
    headers = {"Authorization": "Bearer sk-default-key", "Content-Type": "application/json"}
    
    try:
        # Re-activate token just in case
        with app.app_context():
            Token.query.filter_by(id=11).update({"is_active": True, "error_count": 0})
            from extensions import db
            db.session.commit()

        resp = requests.post("http://localhost:5002/v1/chat/completions", json=payload, headers=headers, timeout=60)
        print(f"Status Code: {resp.status_code}")
        print("Response:")
        print(resp.text)
    except Exception as e:
        print(f"API Request failed: {e}")

if __name__ == "__main__":
    run_test()