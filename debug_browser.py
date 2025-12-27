from playwright.sync_api import sync_playwright
import json
import services
from app import app
from models import Token

def run():
    with app.app_context():
        # 1. Get Token and Cookies
        token_entry = Token.query.get(11)
        if not token_entry:
            print("Token 11 not found")
            return
            
        print(f"Logging in to get cookies for: {token_entry.discord_token[:10]}...")
        handler = services.get_zai_handler()
        result = handler.backend_login(token_entry.discord_token)
        
        if 'error' in result:
            print(f"Login failed: {result['error']}")
            return
            
        cookies_dict = handler.session.cookies.get_dict()
        print(f"Got cookies: {list(cookies_dict.keys())}")
        
        # Prepare cookies for Playwright
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
        browser = p.chromium.launch(headless=True) # Set headless=False to watch
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Add cookies
        context.add_cookies(playwright_cookies)
        
        page = context.new_page()
        
        print("Navigating to https://zai.is/chat ...")
        
        # Setup request interception to catch API calls
        def handle_request(request):
            if "/api/v1/" in request.url:
                print(f"\n[Captured API Request] {request.method} {request.url}")
                print("Headers:")
                print(json.dumps(request.headers, indent=2))
                
        page.on("request", handle_request)
        
        try:
            page.goto("https://zai.is/chat", timeout=30000)
            print("Page loaded. Waiting for network activity...")
            page.wait_for_timeout(10000) # Wait 10s for initial requests
            
            # Try to trigger a models fetch manually if it didn't happen
            print("Evaluating fetch...")
            page.evaluate(
                """
                fetch('/api/v1/models', {\n                    headers: {\n                        'Authorization': 'Bearer " + result.get('token') + "'\n                    }\n                })\n                """
            )
            page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"Error during navigation: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
