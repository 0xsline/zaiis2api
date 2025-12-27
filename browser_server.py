from flask import Flask, jsonify, request
from playwright.sync_api import sync_playwright
import json
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
    data = request.json
    url = data.get('url')
    method = data.get('method', 'GET')
    payload = data.get('payload')
    jwt_token = data.get('token')
    
    # Improved cookie handling: check if 'cookies' key exists even if empty dict
    req_cookies = data.get('cookies')
    if req_cookies is None:
        req_cookies = cached_data["cookies"]

    logger.info(f"Received proxy request: {method} {url} (has_cookies: {req_cookies is not None})")

    if not req_cookies:
        return jsonify({'error': 'not initialized and no cookies provided'}), 400
    
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True, args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1280,720'
            ])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720}
            )
            # Use provided cookies or cached ones
            p_cookies = [{"name": k, "value": v, "domain": "zai.is", "path": "/"} for k, v in req_cookies.items()]
            context.add_cookies(p_cookies)
            page = context.new_page()
            
            # Forward browser console to python logger
            page.on("console", lambda msg: logger.info(f"Browser console: {msg.text}"))
            page.on("pageerror", lambda exc: logger.error(f"Browser page error: {exc}"))

            # Navigate to chat to initialize DarkKnight JS environment
            # and wait for it to make its own requests so we can capture the header.
            dk_header = {"value": None}
            
            def intercept_headers(request):
                header = request.headers.get("x-zai-darkknight")
                if header and not dk_header["value"]:
                    dk_header["value"] = header
                    logger.info("Captured x-zai-darkknight header from page request.")

            page.on("request", intercept_headers)
            
            logger.info("Navigating to zai.is/chat...")
            page.goto("https://zai.is/chat", wait_until="networkidle", timeout=60000)
            
            # Wait for header capture or timeout
            for _ in range(40): # 20 seconds
                if dk_header["value"]: break
                page.wait_for_timeout(500)
            
            if not dk_header["value"]:
                logger.warning("Failed to capture header naturally, waiting a bit more...")
                page.wait_for_timeout(5000)

            method = (method or "GET").upper()
            
            try:
                # Execute fetch directly in the page context. 
                result = page.evaluate("""
                    async ({url, method, payload, token, capturedDK}) => {
                        const headers = {
                            'Authorization': 'Bearer ' + token,
                            'Content-Type': 'application/json'
                        };
                        // If we captured a header, use it as a baseline or backup
                        if (capturedDK) headers['x-zai-darkknight'] = capturedDK;
                        
                        const options = {
                            method: method,
                            headers: headers
                        };
                        if (payload && method !== 'GET') options.body = JSON.stringify(payload);
                        
                        const resp = await fetch(url, options);
                        const text = await resp.text();
                        let body = text;
                        try { body = JSON.parse(text); } catch (e) {}
                        
                        return {
                            status: resp.status,
                            body: body
                        };
                    }
                """, {'url': url, 'method': method, 'payload': payload, 'token': jwt_token, 'capturedDK': dk_header["value"]})
                
                logger.info(f"Fetch completed with status {result.get('status')}")
                return jsonify(result)

            except Exception as e:
                logger.error(f"In-page fetch failed: {e}")
                # Fallback or just report error
                return jsonify({'error': str(e)}), 500
            
        except Exception as e:
            logger.error(f"Proxy error: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            if browser: browser.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
