from playwright.sync_api import sync_playwright
import json
import services
from app import app
from models import Token

def bypass():
    with app.app_context():
        # 1. Get Token
        token_entry = Token.query.get(11)
        if not token_entry:
            print("Token 11 not found")
            return
            
        print(f"Using Discord Token: {token_entry.discord_token[:10]}...")
        
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
        
        # Setup request interception to catch API calls
        captured_headers = {}
        
        def handle_request(request):
            if "/api/v1/" in request.url and "x-zai-darkknight" in request.headers:
                print(f"\n[Captured Header] Found x-zai-darkknight!")
                captured_headers["x-zai-darkknight"] = request.headers["x-zai-darkknight"]
                
        page.on("request", handle_request)
        
        try:
            page.goto("https://zai.is/chat", timeout=60000, wait_until="networkidle")
            print("Page loaded. Checking for captured headers...")
            
            if "x-zai-darkknight" not in captured_headers:
                print("Header not captured yet, waiting...")
                page.wait_for_timeout(5000)
            
            dk_header = captured_headers.get("x-zai-darkknight")
            if not dk_header:
                print("Failed to capture x-zai-darkknight header.")
                return

            print(f"Using captured header: {dk_header[:50]}...")

            print("Executing fetch('/api/v1/models') with captured header...")
            response_data = page.evaluate("""
                async ({token, dk_header}) => {
                    const resp = await fetch('https://zai.is/api/v1/models', {
                        method: 'GET',
                        headers: {
                            'Authorization': 'Bearer ' + token,
                            'Content-Type': 'application/json',
                            'x-zai-darkknight': dk_header
                        }
                    });
                    const text = await resp.text();
                    return {
                        status: resp.status,
                        headers: Object.fromEntries(resp.headers),
                        body: text
                    };
                }
            """, {'token': jwt_token, 'dk_header': dk_header})
            
            print(f"\nStatus: {response_data['status']}")
            print(f"Body: {response_data['body'][:500]}...") # Print first 500 chars
            
            if response_data['status'] == 200:
                print("\n[SUCCESS] Successfully bypassed DarkKnight protection!")
                try:
                    data = json.loads(response_data['body'])
                    models = [m['id'] for m in data.get('data', [])]
                    print("\n[Models Found]:")
                    for model in models:
                        print(f" - {model}")
                except Exception as e:
                    print(f"Error parsing models: {e}")
            else:
                print("\n[FAILED] Still blocked or other error.")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    bypass()
