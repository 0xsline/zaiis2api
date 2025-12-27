import os
import time
import logging
import json
import hashlib
import sqlite3
from datetime import datetime
from threading import Lock
from flask import Flask, request, jsonify, render_template, send_from_directory, Response, stream_with_context
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
import requests

from extensions import db
from models import SystemConfig, Token, RequestLog
import services

# Browser Service Config
BROWSER_SERVICE_URL = os.environ.get("BROWSER_SERVICE_URL", "http://localhost:5006")
_browser_initialized = False

def _ensure_browser_service_initialized():
    global _browser_initialized
    if _browser_initialized: return
    try:
        token = Token.query.filter_by(is_active=True).first()
        if not token: return
        handler = services.get_zai_handler()
        res = handler.backend_login(token.discord_token)
        if 'error' not in res:
            cookies = handler.session.cookies.get_dict()
            requests.post(f"{BROWSER_SERVICE_URL}/init", json={'cookies': cookies}, timeout=5)
            _browser_initialized = True
    except: pass

def _browser_proxy_request(url, method, payload, token):
    _ensure_browser_service_initialized()
    try:
        resp = requests.post(f"{BROWSER_SERVICE_URL}/proxy", json={
            'url': url,
            'method': method,
            'payload': payload,
            'token': token
        }, timeout=120)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Browser proxy request failed: {e}")
    return None

# Initialize App
app = Flask(__name__, static_folder='static', template_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI', 'sqlite:///zai2api.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-me')

db.init_app(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    config = SystemConfig.query.first()
    if config and str(config.id) == user_id:
        return User(id=str(config.id), username=config.admin_username)
    return None

def migrate_sqlite_schema():
    path = None
    try:
        engine = db.engine
        if getattr(engine.url, 'drivername', None) == 'sqlite':
            path = engine.url.database
    except: pass
    if not path:
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if uri and uri.startswith('sqlite:///'): path = uri[len('sqlite:///'):]
    if not path: return
    dir_name = os.path.dirname(path)
    if dir_name: os.makedirs(dir_name, exist_ok=True)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(system_config)")
        sc_cols = {row[1] for row in cursor.fetchall()}
        if sc_cols:
            if 'error_retry_count' not in sc_cols: cur.execute("ALTER TABLE system_config ADD COLUMN error_retry_count INTEGER DEFAULT 3")
            if 'token_refresh_interval' not in sc_cols: cur.execute("ALTER TABLE system_config ADD COLUMN token_refresh_interval INTEGER DEFAULT 3600")
            if 'stream_conversion_enabled' not in sc_cols: cur.execute("ALTER TABLE system_config ADD COLUMN stream_conversion_enabled BOOLEAN DEFAULT 0")
        cursor.execute("PRAGMA table_info(request_log)")
        rl_cols = {row[1] for row in cursor.fetchall()}
        if rl_cols:
            if 'discord_token' not in rl_cols: cur.execute("ALTER TABLE request_log ADD COLUMN discord_token TEXT")
            if 'zai_token' not in rl_cols: cur.execute("ALTER TABLE request_log ADD COLUMN zai_token TEXT")
        conn.commit()
    finally: conn.close()

def _mask_token(value: str | None, head: int = 12, tail: int = 6) -> str | None:
    if not value: return None
    if len(value) <= head + tail: return value
    return f"{value[:head]}...{value[-tail:]}"

def _dt_iso(dt): return dt.replace(microsecond=0).isoformat() if dt else None

def init_db():
    with app.app_context():
        db.create_all()
        migrate_sqlite_schema()
        db.create_all()
        config = SystemConfig.query.first()
        if not config:
            config = SystemConfig(admin_username='admin', admin_password_hash=generate_password_hash('admin'))
            db.session.add(config)
            db.session.commit()
        try:
            seconds = int(getattr(config, 'token_refresh_interval', 3600) or 3600)
            scheduler.reschedule_job('token_refresher', trigger='interval', seconds=seconds)
        except: pass

def scheduled_refresh():
    with app.app_context(): services.refresh_all_tokens()

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_refresh, 'interval', seconds=3600, id='token_refresher')
scheduler.start()

@app.route('/login')
def login_page(): return send_from_directory('static', 'login.html')
@app.route('/manage')
def manage_page(): return send_from_directory('static', 'manage.html')
@app.route('/')
def index(): return send_from_directory('static', 'login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username, password = data.get('username'), data.get('password')
    config = SystemConfig.query.first()
    if config and config.admin_username == username and check_password_hash(config.admin_password_hash, password):
        user = User(id=str(config.id), username=config.admin_username)
        login_user(user)
        import jwt
        token = jwt.encode({'user_id': str(config.id), 'exp': datetime.utcnow().timestamp() + 86400}, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({'success': True, 'token': token})
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

def check_auth_token():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        import jwt
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return payload.get('user_id')
        except: return None
    return None

def api_auth_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS': return f(*args, **kwargs)
        if not check_auth_token(): return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/stats', methods=['GET'])
@api_auth_required
def api_stats():
    total_tokens = Token.query.count()
    active_tokens = Token.query.filter_by(is_active=True).count()
    total_images = Token.query.with_entities(db.func.sum(Token.image_count)).scalar() or 0
    total_videos = Token.query.with_entities(db.func.sum(Token.video_count)).scalar() or 0
    total_errors = Token.query.with_entities(db.func.sum(Token.error_count)).scalar() or 0
    return jsonify({'total_tokens': total_tokens, 'active_tokens': active_tokens, 'today_images': 0, 'total_images': total_images, 'today_videos': 0, 'total_videos': total_videos, 'today_errors': 0, 'total_errors': total_errors})

@app.route('/api/tokens', methods=['GET'])
@api_auth_required
def get_tokens():
    tokens = Token.query.all()
    config = SystemConfig.query.first()
    result = []
    for t in tokens:
        result.append({'id': t.id, 'email': t.email, 'is_active': t.is_active, 'at_expires': _dt_iso(t.at_expires), 'credits': t.credits, 'user_paygate_tier': t.user_paygate_tier, 'current_project_name': t.current_project_name, 'current_project_id': t.current_project_id, 'image_count': t.image_count, 'video_count': t.video_count, 'error_count': t.error_count, 'remark': t.remark, 'image_enabled': t.image_enabled, 'video_enabled': t.video_enabled, 'image_concurrency': t.image_concurrency, 'video_concurrency': t.video_concurrency, 'zai_token': t.zai_token, 'st': t.discord_token})
    return jsonify({'tokens': result, 'config': {'token_refresh_interval': config.token_refresh_interval if config else 3600}})

@app.route('/api/tokens', methods=['POST'])
@api_auth_required
def add_token():
    data = request.json
    st = data.get('st')
    if not st: return jsonify({'success': False, 'message': 'Missing Discord Token'}), 400
    token = Token(discord_token=st, remark=data.get('remark'), current_project_id=data.get('project_id'), current_project_name=data.get('project_name'), image_enabled=data.get('image_enabled', True), video_enabled=data.get('video_enabled', True), image_concurrency=data.get('image_concurrency', -1), video_concurrency=data.get('video_concurrency', -1))
    db.session.add(token)
    db.session.commit()
    success, msg = services.update_token_info(token.id)
    return jsonify({'success': True, 'message': msg if not success else None})

@app.route('/api/tokens/<int:id>', methods=['PUT', 'DELETE'])
@api_auth_required
def handle_token(id):
    token = Token.query.get_or_404(id)
    if request.method == 'DELETE':
        db.session.delete(token)
        db.session.commit()
        return jsonify({'success': True})
    data = request.json
    for key in ['st', 'remark', 'project_id', 'project_name', 'image_enabled', 'video_enabled', 'image_concurrency', 'video_concurrency']:
        if key in data: setattr(token, key if key != 'st' else 'discord_token', data[key])
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/tokens/refresh-all', methods=['POST'])
@api_auth_required
def refresh_all_tokens_endpoint():
    try:
        services.refresh_all_tokens(force=True)
        return jsonify({'success': True, 'message': '所有 Token 刷新请求已发送'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)})

@app.route('/api/tokens/<int:id>/test', methods=['POST'])
@api_auth_required
def test_token(id):
    success, msg = services.update_token_info(id)
    token = Token.query.get(id)
    if success: return jsonify({'success': True, 'status': 'success', 'email': token.email})
    return jsonify({'success': False, 'message': msg})

# --- OpenAI Compatible Proxy ---

_rr_lock = Lock()
_rr_index = 0

def _get_token_candidates():
    global _rr_index
    tokens = Token.query.filter_by(is_active=True).order_by(Token.id.asc()).all()
    valid_tokens = [t for t in tokens if t.zai_token and not str(t.zai_token).startswith('SESSION')]
    if not valid_tokens: return []
    with _rr_lock:
        start = _rr_index % len(valid_tokens)
        _rr_index = (start + 1) % len(valid_tokens)
    return valid_tokens[start:] + valid_tokens[:start]

def _mark_token_error(token: Token, config: SystemConfig, reason: str):
    token.error_count = int(token.error_count or 0) + 1
    token.remark = (reason or '')[:1000]
    if token.error_count >= (config.error_ban_threshold or 3):
        token.is_active = False
        token.remark = f"Auto-banned: {(reason or '')[:950]}"
    db.session.commit()

@app.route('/v1/chat/completions', methods=['POST'])
def proxy_chat_completions():
    start_time = time.time()
    config = SystemConfig.query.first()
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header.split(' ')[1] != config.api_key: return jsonify({'error': 'Invalid API Key'}), 401
    payload = request.get_json(silent=True)
    candidates = _get_token_candidates()
    if not candidates: return jsonify({'error': 'No active tokens available'}), 503

    for token in candidates:
        logger.info(f"Using token {token.id} for request...")
        res = _browser_proxy_request("https://zai.is/api/v1/chat/completions", "POST", payload, token.zai_token)
        if not res or 'error' in res:
            error_msg = res.get('error', 'Browser proxy failed') if res else 'Network Error'
            _mark_token_error(token, config, error_msg)
            continue
        
        # Result is {status, body}
        duration = time.time() - start_time
        log = RequestLog(operation="chat/completions", token_email=token.email, discord_token=_mask_token(token.discord_token), zai_token=_mask_token(token.zai_token), status_code=res.get('status'), duration=duration)
        db.session.add(log)
        db.session.commit()

        if res.get('status', 0) >= 400:
            _mark_token_error(token, config, str(res.get('body')))
            continue

        token.error_count = 0
        db.session.commit()
        return jsonify(res.get('body'))

    return jsonify({'error': 'All candidates failed'}), 503

@app.route('/v1/models', methods=['GET'])
def proxy_models():
    config = SystemConfig.query.first()
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header.split(' ')[1] != config.api_key: return jsonify({'error': 'Invalid API Key'}), 401
    token = Token.query.filter_by(is_active=True).first()
    if not token: return jsonify({"object": "list", "data": []})
    
    res = _browser_proxy_request("https://zai.is/api/v1/models", "GET", None, token.zai_token)
    if res and res.get('status') == 200:
        return jsonify(res.get('body'))
    return jsonify({"error": "Failed to fetch models"}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5003, debug=True, use_reloader=False)
