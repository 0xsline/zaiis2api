from playwright.sync_api import sync_playwright
import json
import services
from app import app
from models import Token

def test_chat():
    with app.app_context():
        # 1. Get Token
        token_entry = Token.query.first()
        if not token_entry:
            print("No tokens found in database")
            return
            
        print(f"Using Discord Token (ID: {token_entry.id}): {token_entry.discord_token[:10]}...")
        
        # 2. Get Cookies & JWT
        handler = services.get_zai_handler()
        result = handler.backend_login(token_entry.discord_token)
        if 'error' in result:
            print(f"Login failed: {result['error']}")
            return
            
        cookies_dict = handler.session.cookies.get_dict()
        jwt_token = result.get('token')
        
        playwright_cookies = []
        for name, value in cookies_dict.items():
            playwright_cookies.append({
                "name": name,
                "value": value,
                "domain": "zai.is",
                "path": "/"
            })

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_cookies(playwright_cookies)
        page = context.new_page()
        
        # Setup request interception to capture header
        captured_headers = {}
        def handle_request(request):
            if "/api/v1/" in request.url and "x-zai-darkknight" in request.headers:
                captured_headers["x-zai-darkknight"] = request.headers["x-zai-darkknight"]
        page.on("request", handle_request)
        
        try:
            print("Navigating to https://zai.is/chat ...")
            page.goto("https://zai.is/chat", timeout=60000, wait_until="networkidle")
            
            if "x-zai-darkknight" not in captured_headers:
                print("Waiting for header...")
                page.wait_for_timeout(5000)
            
            dk_header = captured_headers.get("x-zai-darkknight")
            if not dk_header:
                print("Failed to capture x-zai-darkknight header.")
                return

            print(f"Captured Header: {dk_header[:30]}...")

            print("Sending Chat Completion Request (Model: gemini-3-flash-preview)...")
            chat_payload = {
                "model": "gemini-3-flash-preview",
                "messages": [{"role": "user", "content": "Hello! Who are you?"}],
                "stream": False
            }
            
            response_data = page.evaluate(
                """
                async ({token, dk_header, payload}) => {
                    const resp = await fetch('https://zai.is/api/v1/chat/completions', {
                        method: 'POST',
                        headers: {
                            'Authorization': 'Bearer ' + token,
                            'Content-Type': 'application/json',
                            'x-zai-darkknight': dk_header
                        },
                        body: JSON.stringify(payload)
                    });
                    const text = await resp.text();
                    return {
                        status: resp.status,
                        headers: Object.fromEntries(resp.headers),
                        body: text
                    };
                }
            """, {'token': jwt_token, 'dk_header': dk_header, 'payload': chat_payload})
            
            print(f"\nStatus: {response_data['status']}")
            print(f"Response: {response_data['body']}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_chat()
