from flask import Flask, jsonify, request
from playwright.sync_api import sync_playwright
import json
import time
import logging
import os
import threading
import queue
import uuid

# Config
PORT = int(os.environ.get('PORT', 5006))
# Remote debugging port for local Chrome
CDP_URL = "http://127.0.0.1:9222"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global Queues
request_queue = queue.Queue()
response_queues = {} 

# Global State for Worker
worker_state = {
    "cookies": None,
    "pages": {} 
}

def browser_worker():
    """Single dedicated thread for all Playwright interactions using CDP connection"""
    logger.info("Browser Worker Thread Started (CDP Connection Mode)")
    
    # ENSURE NO PROXY for CDP connection
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,*"
    
    with sync_playwright() as p:
        while True:
            try:
                req = request_queue.get()
                req_id, req_type, data = req
                
                logger.info(f"Worker processing request {req_id} ({req_type})")
                
                result = None
                try:
                    if req_type == 'init':
                        result = _handle_init(data)
                    elif req_type == 'proxy':
                        result = _handle_proxy(p, data)
                    else:
                        result = {'error': 'unknown request type'}
                except Exception as e:
                    logger.error(f"Worker error processing {req_id}: {e}")
                    result = {'error': str(e)}
                
                if req_id in response_queues:
                    response_queues[req_id].put(result)
                
                request_queue.task_done()
                
            except Exception as e:
                logger.error(f"Critical Worker Loop Error: {e}")
                time.sleep(1)

def _handle_init(data):
    cookies = data.get('cookies')
    if cookies:
        worker_state["cookies"] = cookies
        return {'status': 'ready'}
    return {'error': 'no cookies'}

def _get_or_create_page(p, jwt_token, req_cookies):
    if jwt_token in worker_state["pages"]:
        entry = worker_state["pages"][jwt_token]
        try:
            if not entry['page'].is_closed():
                entry['last_used'] = time.time()
                return entry['page']
        except:
            del worker_state["pages"][jwt_token]

    logger.info(f"[{jwt_token[:6]}] Connecting to existing Chrome via CDP...")
    
    try:
        # CONNECT instead of LAUNCH
        browser = p.chromium.connect_over_cdp(CDP_URL)
        # Use existing context or create new one if needed. 
        # Ideally we use the default context of the opened browser to share everything.
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        
        # Inject cookies
        p_cookies = [{"name": k, "value": v, "domain": "zai.is", "path": "/"} for k, v in req_cookies.items()]
        context.add_cookies(p_cookies)
        
        page = context.new_page()
        
        page.add_init_script("""
            window._latestDK = null;
            const originalFetch = window.fetch;
            window.fetch = async function(...args) {
                const req = new Request(...args);
                const dk = req.headers.get('x-zai-darkknight');
                if (dk) window._latestDK = dk;
                return originalFetch(...args);
            };
        """)
        
        page.on("console", lambda msg: logger.info(f"[{jwt_token[:6]}] Console: {msg.text}"))
        
        logger.info(f"[{jwt_token[:6]}] Navigating to chat...")
        page.goto("https://zai.is/chat", wait_until="domcontentloaded", timeout=30000)
        
        # Warm up
        page.wait_for_timeout(3000)
        try:
            page.evaluate("fetch('/api/v1/models').catch(e => {})")
        except: pass
        
        worker_state["pages"][jwt_token] = {
            'browser': browser,
            'context': context, # Don't close context on cleanup if it's shared
            'page': page,
            'last_used': time.time()
        }
        return page
        
    except Exception as e:
        logger.error(f"Failed to connect to CDP: {e}")
        raise Exception(f"Could not connect to Chrome on {CDP_URL}. Please ensure Chrome is running with --remote-debugging-port=9222")

def _handle_proxy(p, data):
    url = data.get('url')
    method = data.get('method', 'GET')
    payload = data.get('payload')
    jwt_token = data.get('token')
    req_cookies = data.get('cookies') or worker_state["cookies"]
    
    if not req_cookies or not jwt_token:
        return {'error': 'missing cookies or token'}
        
    try:
        page = _get_or_create_page(p, jwt_token, req_cookies)
        
        result = page.evaluate("""
            async ({url, method, payload, token}) => {
                const headers = {
                    'Authorization': 'Bearer ' + token,
                    'Content-Type': 'application/json'
                };
                if (window._latestDK) headers['x-zai-darkknight'] = window._latestDK;
                
                const options = {
                    method: method,
                    headers: headers
                };
                if (payload && method !== 'GET') options.body = JSON.stringify(payload);
                
                const resp = await fetch(url, options);
                let body = await resp.text();
                try { body = JSON.parse(body); } catch (e) {}
                
                return {
                    status: resp.status,
                    body: body
                };
            }
        """, {'url': url, 'method': method, 'payload': payload, 'token': jwt_token})
        
        return result
    except Exception as e:
        logger.error(f"Proxy execution error: {e}")
        # Only clear cache if page is truly dead
        if jwt_token in worker_state["pages"]:
            try: worker_state["pages"][jwt_token]['page'].close() 
            except: pass
            del worker_state["pages"][jwt_token]
        return {'error': str(e)}

@app.route('/init', methods=['POST'])
def init_route():
    req_id = str(uuid.uuid4())
    q = queue.Queue()
    response_queues[req_id] = q
    request_queue.put((req_id, 'init', request.json))
    try:
        result = q.get(timeout=30)
        del response_queues[req_id]
        return jsonify(result)
    except:
        return jsonify({'error': 'timeout'}), 504

@app.route('/proxy', methods=['POST'])
def proxy_route():
    logger.info(f"Received proxy request from app.py: {request.json.get('url')}")
    req_id = str(uuid.uuid4())
    q = queue.Queue()
    response_queues[req_id] = q
    request_queue.put((req_id, 'proxy', request.json))
    try:
        result = q.get(timeout=120) 
        del response_queues[req_id]
        return jsonify(result)
    except:
        return jsonify({'error': 'timeout'}), 504

if __name__ == '__main__':
    t = threading.Thread(target=browser_worker, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=PORT, threaded=True, use_reloader=False)