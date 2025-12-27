from flask import Flask, jsonify, request
from playwright.sync_api import sync_playwright
import time
import logging
import os

# Config
PORT = int(os.environ.get('PORT', 5006))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global storage for state
cached_data = {
    "cookies": None
}

@app.route('/init', methods=['POST'])
def init_browser():
    data = request.json
    cookies = data.get('cookies')
    if cookies:
        cached_data["cookies"] = cookies
        logger.info("Cookies updated.")
        return jsonify({'status': 'ready'})
    return jsonify({'error': 'no cookies'}), 400

@app.route('/proxy', methods=['POST'])
def proxy_request():
    """Execute a request inside the real browser context to bypass all protections."""
    if not cached_data["cookies"]:
        return jsonify({'error': 'not initialized'}), 400
        
    data = request.json
    url = data.get('url')
    method = data.get('method', 'GET')
    payload = data.get('payload')
    jwt_token = data.get('token')

    logger.info(f"Proxying {method} request to {url}...")
    
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            p_cookies = [{"name": k, "value": v, "domain": "zai.is", "path": "/"} for k, v in cached_data["cookies"].items()]
            context.add_cookies(p_cookies)
            page = context.new_page()
            
            # Navigate to chat to initialize DarkKnight JS environment
            page.goto("https://zai.is/chat", wait_until="domcontentloaded", timeout=60000)
            
            # Execute the request inside the browser using evaluate
            # This ensures the frontend SDK interceptors add the correct x-zai-darkknight header
            result = page.evaluate("""
                async ({url, method, payload, token}) => {
                    const options = {
                        method: method,
                        headers: {
                            'Authorization': 'Bearer ' + token,
                            'Content-Type': 'application/json'
                        }
                    };
                    if (payload) options.body = JSON.stringify(payload);
                    
                    const resp = await fetch(url, options);
                    const text = await resp.text();
                    let body = text;
                    try { body = JSON.parse(text); } catch(e) {}
                    
                    return {
                        status: resp.status,
                        body: body
                    };
                }
            """, {'url': url, 'method': method, 'payload': payload, 'token': jwt_token})
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Proxy error: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            if browser: browser.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)