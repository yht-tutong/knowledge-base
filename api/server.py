from flask import Flask, request, session, jsonify, redirect, send_from_directory
from api.category_routes import category_bp
from api.knowledge_routes import knowledge_bp
from api.tag_routes import tag_bp
from api.backup_routes import backup_bp
from api.operation_routes import operation_bp
from api.log_routes import log_bp
from api.auth_routes import auth_bp, login_required, set_password_hash, check_auth, hash_password, generate_password
from models.database import Database
from utils.config import load_config, save_config, hash_password as config_hash_password
import secrets
import time
import os
import logging
from collections import defaultdict
from datetime import timedelta


_rate_limit_store = defaultdict(list)


def create_app(debug=False, password_hash=None, ssl_context=None):
    Database().init_db()
    app = Flask(__name__, static_folder='../static', static_url_path='')
    app.secret_key = secrets.token_hex(32)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    if ssl_context:
        app.config['SESSION_COOKIE_SECURE'] = True
    if debug:
        app.config['DEBUG'] = True
    app.register_blueprint(category_bp, url_prefix='/api')
    app.register_blueprint(knowledge_bp, url_prefix='/api')
    app.register_blueprint(tag_bp, url_prefix='/api')
    app.register_blueprint(backup_bp, url_prefix='/api')
    app.register_blueprint(operation_bp, url_prefix='/api')
    app.register_blueprint(log_bp, url_prefix='/api')
    app.register_blueprint(auth_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
        return response

    if password_hash is not None:
        set_password_hash(password_hash)

    if debug:
        @app.before_request
        def log_request():
            logging.getLogger('knowledge_base').debug('Request: %s %s', request.method, request.path)

    @app.before_request
    def check_login():
        # 如果配置关闭了登录验证，跳过认证
        config = load_config()
        if config.get('disable_login', False) or not config.get('password_hash', ''):
            return None

        # 速率限制：API 和认证接口
        if request.path.startswith('/api/') or request.path.startswith('/auth/'):
            ip = request.remote_addr or '127.0.0.1'
            now = time.time()
            max_req = 10 if request.path == '/auth/login' else 60
            _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if now - t < 60]
            if len(_rate_limit_store[ip]) >= max_req:
                return jsonify({'code': 429, 'message': '请求过于频繁，请稍等一分钟'}), 429
            _rate_limit_store[ip].append(now)

        # 允许登录页面和认证接口
        if request.path.startswith('/auth/') or request.path == '/login' or request.path.startswith('/css/') or request.path.startswith('/js/'):
            return None
        # API 请求返回 401
        if request.path.startswith('/api/'):
            if not check_auth():
                return jsonify({'code': 401, 'message': '请先登录'}), 401
        # 页面请求重定向到登录页
        elif not check_auth():
            return redirect('/login')
        return None

    @app.route('/')
    def index():
        return app.send_static_file('index.html')

    @app.route('/login')
    def login_page():
        if session.get('authenticated'):
            return redirect('/')
        config = load_config()
        if not config.get('password_hash', '') or config.get('disable_login', False):
            return redirect('/')
        return app.send_static_file('login.html')

    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
        return send_from_directory(upload_dir, filename)

    @app.route('/api/config', methods=['GET'])
    def get_config():
        config = load_config()
        return jsonify({
            'code': 200,
            'data': {
                'has_password': bool(config.get('password_hash', '')),
                'enable_startup_backup': config.get('enable_startup_backup', True),
                'debug': config.get('debug', False),
                'disable_login': config.get('disable_login', False)
            }
        })

    @app.route('/api/config', methods=['POST'])
    def update_config():
        body = request.get_json(silent=True)
        if not body:
            return jsonify({'code': 400, 'message': '无效的请求数据'}), 400
        config = load_config()
        if body.get('password'):
            config['password_hash'] = config_hash_password(body['password'])
            set_password_hash(config['password_hash'])
        if 'enable_startup_backup' in body:
            config['enable_startup_backup'] = bool(body['enable_startup_backup'])
        if 'debug' in body:
            config['debug'] = bool(body['debug'])
        if 'disable_login' in body:
            config['disable_login'] = bool(body['disable_login'])
        save_config(config)
        return jsonify({'code': 200, 'message': '配置已保存'})

    return app