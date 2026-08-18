"""认证 API 路由"""
import hashlib
import secrets
import time
from collections import defaultdict
from flask import Blueprint, request, session, jsonify, redirect

auth_bp = Blueprint('auth', __name__)

# 登录防暴力破解
_login_failures = defaultdict(list)  # ip -> [timestamp, ...]
LOCKOUT_COUNT = 5       # 5 次失败
LOCKOUT_WINDOW = 300    # 5 分钟内
LOCKOUT_DURATION = 900  # 锁定 15 分钟

# 全局密码哈希（启动时设置）
_password_hash = None

def set_password_hash(hash_val):
    global _password_hash
    _password_hash = hash_val

def check_auth():
    """检查是否已登录，返回 True/False"""
    return session.get('logged_in') == True

def hash_password(password):
    """SHA256 哈希密码"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_password(length=12):
    """生成随机密码"""
    return secrets.token_urlsafe(length)

def login_required(f):
    """API 登录检查装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            return jsonify({'code': 401, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated

@auth_bp.route('/auth/login', methods=['POST'])
def login():
    ip = request.remote_addr or '127.0.0.1'
    now = time.time()

    # 清理过期记录
    _login_failures[ip] = [t for t in _login_failures[ip] if now - t < LOCKOUT_DURATION]

    # 检查是否被锁定
    recent_failures = [t for t in _login_failures[ip] if now - t < LOCKOUT_DURATION]
    if len(recent_failures) >= LOCKOUT_COUNT:
        return jsonify({'code': 429, 'message': '登录尝试过多，请15分钟后再试'}), 429

    body = request.get_json() or {}
    password = body.get('password', '')
    if hash_password(password) == _password_hash:
        # 登录成功，清除失败记录
        _login_failures.pop(ip, None)
        session['logged_in'] = True
        session.permanent = True
        return jsonify({'code': 200, 'data': {'message': '登录成功'}})

    # 记录失败
    _login_failures[ip].append(now)
    return jsonify({'code': 401, 'message': '密码错误'}), 401

@auth_bp.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'code': 200, 'data': {'message': '已登出'}})

@auth_bp.route('/auth/status', methods=['GET'])
def status():
    return jsonify({'code': 200, 'data': {'logged_in': check_auth()}})

@auth_bp.route('/auth/restart-login', methods=['POST'])
def restart_login():
    """重启后自动登录：验证一次性令牌"""
    from utils.config import load_config, save_config
    body = request.get_json() or {}
    token = body.get('token', '')
    config = load_config()
    saved_token = config.get('restart_token', '')
    if token and saved_token and token == saved_token:
        session['logged_in'] = True
        session.permanent = True
        config['restart_token'] = ''
        save_config(config)
        return jsonify({'code': 200, 'data': {'message': '自动登录成功'}})
    return jsonify({'code': 401, 'message': '令牌无效'}), 401