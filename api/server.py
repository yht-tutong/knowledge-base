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
import re
import logging
import shutil
import sys
import glob as glob_mod
from collections import defaultdict
from datetime import timedelta


_rate_limit_store = defaultdict(list)


def _setup_werkzeug_logger(debug, log_file):
    """配置 Werkzeug HTTP 请求日志：
    - 始终写入日志文件
    - 调试模式下也输出到终端
    - 非调试模式下关闭终端输出
    """
    wz_log = logging.getLogger('werkzeug')
    wz_log.setLevel(logging.DEBUG)
    # 清除默认 handler
    wz_log.handlers = []
    # 阻止 propagate 到 root logger（避免重复输出）
    wz_log.propagate = False

    # 文件 handler：始终写入（保留级别前缀）
    if log_file:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        wz_log.addHandler(fh)

    # 控制台 handler：仅调试模式，无级别前缀，仅颜色
    if debug:
        class WerkzeugConsoleFormatter(logging.Formatter):
            COLORS = {
                'ERROR': '\033[91m',
                'WARNING': '\033[93m',
                'INFO': '\033[92m',
                'DEBUG': '\033[90m',
            }
            RESET = '\033[0m'

            def format(self, record):
                msg = record.getMessage()
                # Debugger 消息不加颜色
                if 'Debugger' in msg:
                    return msg
                # reloader 消息用 WARNING 颜色
                if 'Detected change' in msg or 'Restarting with stat' in msg:
                    return f"\033[93m{msg}\033[0m"
                # 无请求行的时间戳/连接日志：不加颜色
                if '"' not in msg:
                    return msg
                # HTTP 请求行：只给引号内 "METHOD /path HTTP/1.1" 加颜色
                method_colors = {'POST': '\033[92m', 'DELETE': '\033[91m', 'PUT': '\033[93m', 'PATCH': '\033[93m'}
                m = re.search(r'^(\S+ \S+ \S+ \[[^\]]+\] )(".+?")(.*)', msg)
                if not m:
                    # 不完整的请求行：仅 POST/DELETE/PUT/PATCH 着色，GET 无色，" 本身无色
                    qm = re.search(r'"(\w+)', msg)
                    if qm and qm.group(1) in method_colors:
                        idx = qm.start()
                        return msg[:idx+1] + f"{method_colors[qm.group(1)]}{msg[idx+1:]}{self.RESET}"
                    return msg
                prefix = m.group(1)   # 127.0.0.1 - - [18/Aug/2026 00:47:08]
                quoted = m.group(2)   # "GET / HTTP/1.1"
                suffix = m.group(3)   # 200 -
                # 按方法优先着色，" 本身无色
                mm = re.search(r'"(\w+)', quoted)
                if mm:
                    color = method_colors.get(mm.group(1), '')
                    if color:
                        return prefix + '"' + f"{color}{quoted[1:-1]}{self.RESET}" + '"' + suffix
                # 根据状态码决定颜色
                sm = re.search(r'(\d{3})', suffix)
                if sm:
                    code = sm.group(1)
                    if code.startswith('2'):
                        color = ''       # 2xx 无色
                    elif code.startswith('3'):
                        color = ''       # 3xx 无色
                    elif code.startswith('4'):
                        color = '\033[93m'  # 4xx 黄色
                    elif code.startswith('5'):
                        color = '\033[91m'  # 5xx 红色
                    else:
                        color = ''
                    if color:
                        return prefix + '"' + f"{color}{quoted[1:-1]}{self.RESET}" + '"' + suffix
                return prefix + quoted + suffix

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(WerkzeugConsoleFormatter())
        wz_log.addHandler(ch)


def create_app(debug=False, password_hash=None, ssl_context=None, log_file=None):
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

    # 配置 Werkzeug HTTP 请求日志
    _setup_werkzeug_logger(debug, log_file)
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
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'"
        return response

    if password_hash is not None:
        set_password_hash(password_hash)

    if debug:
        @app.before_request
        def log_request():
            logging.getLogger('knowledge_base').debug('Request: %s %s', request.method, request.path)

        from flask import got_request_exception
        def _log_exception(sender, exception, **extra):
            logging.getLogger('knowledge_base').error('Error: %s', str(exception))
        got_request_exception.connect(_log_exception, app)

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
                'disable_login': config.get('disable_login', False),
                'enable_temp_password': config.get('enable_temp_password', False)
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
        if 'enable_temp_password' in body:
            was_temp = config.get('enable_temp_password', False)
            config['enable_temp_password'] = bool(body['enable_temp_password'])
            if config['enable_temp_password'] and not was_temp:
                # 仅在从非临时密码模式切换到临时密码模式时重置
                config['password_hash'] = ''
                config['temp_password_initialized'] = False
        save_config(config)
        return jsonify({'code': 200, 'message': '配置已保存'})

    @app.route('/api/system/restart', methods=['POST'])
    def restart_system():
        """重启系统：仅重启程序，不删除数据"""
        # 生成一次性重启令牌，使重启后自动登录
        import secrets
        config = load_config()
        restart_token = secrets.token_urlsafe(32)
        config['restart_token'] = restart_token
        save_config(config)

        def restart():
            time.sleep(0.5)
            os.environ['TEMP_PWD_KEEP'] = '1'
            os.execv(sys.executable, [sys.executable] + sys.argv)

        import threading
        threading.Thread(target=restart, daemon=True).start()

        return jsonify({'code': 200, 'data': {'message': '系统正在重启', 'restart_token': restart_token}})

    @app.route('/api/system/clear-cache', methods=['POST'])
    def clear_cache():
        """清除缓存：删除日志和 __pycache__"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        deleted_logs = 0
        deleted_pycache = 0

        # 删除日志目录
        logs_dir = os.path.join(base_dir, 'logs')
        if os.path.exists(logs_dir):
            try:
                shutil.rmtree(logs_dir)
                deleted_logs = 1
            except OSError:
                pass
            os.makedirs(logs_dir, exist_ok=True)

        # 删除 __pycache__ 目录
        for dirpath, dirnames, _ in os.walk(base_dir):
            if '__pycache__' in dirnames:
                pc_dir = os.path.join(dirpath, '__pycache__')
                try:
                    shutil.rmtree(pc_dir)
                    deleted_pycache += 1
                except OSError:
                    pass

        # 生成重启令牌，使重启后自动登录
        import secrets
        config = load_config()
        restart_token = secrets.token_urlsafe(32)
        config['restart_token'] = restart_token
        save_config(config)

        # 延迟重启程序
        def restart():
            time.sleep(0.5)
            os.environ['TEMP_PWD_KEEP'] = '1'
            os.execv(sys.executable, [sys.executable] + sys.argv)

        import threading
        threading.Thread(target=restart, daemon=True).start()

        return jsonify({
            'code': 200,
            'data': {
                'message': f'缓存已清除，正在重启',
                'restart_token': restart_token
            }
        })

    @app.route('/api/system/reset', methods=['POST'])
    def reset_system():
        """重置系统：删除所有数据并关闭程序"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        items_to_delete = [
            'knowledge.db',
            'knowledge.db-wal',
            'knowledge.db-shm',
        ]
        dirs_to_delete = ['logs', 'backups']

        # 删除文件
        for item in items_to_delete:
            fp = os.path.join(base_dir, item)
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass

        # 删除目录
        for d in dirs_to_delete:
            dp = os.path.join(base_dir, d)
            if os.path.exists(dp):
                try:
                    shutil.rmtree(dp)
                except OSError:
                    pass

        # 删除 uploads 目录
        uploads_dir = os.path.join(base_dir, 'static', 'uploads')
        if os.path.exists(uploads_dir):
            try:
                shutil.rmtree(uploads_dir)
            except OSError:
                pass

        # 删除所有 __pycache__
        for dirpath, dirnames, _ in os.walk(base_dir):
            if '__pycache__' in dirnames:
                pc_dir = os.path.join(dirpath, '__pycache__')
                try:
                    shutil.rmtree(pc_dir)
                except OSError:
                    pass

        # 延迟重启程序
        def restart():
            time.sleep(0.5)
            os.environ['TEMP_PWD_KEEP'] = '1'
            os.execv(sys.executable, [sys.executable] + sys.argv)

        import threading
        threading.Thread(target=restart, daemon=True).start()

        return jsonify({'code': 200, 'data': {'message': '系统已重置，正在重启'}})

    return app