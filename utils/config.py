"""配置管理模块 - 独立于数据库，不随数据库重置而丢失"""
import os
import sys
import json
import hashlib
import secrets
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

DEFAULT_CONFIG = {
    'password_hash': '',              # SHA256 密码哈希
    'enable_startup_backup': True,    # 启动时自动备份
    'debug': False,                   # 调试模式
    'disable_login': True,            # 关闭登录验证（默认关闭）
    'enable_temp_password': False,    # 启用临时密码（默认关闭）
    'ssl_cert': '',                   # SSL 证书路径
    'ssl_key': '',                    # SSL 私钥路径
    'first_run': True,                # 是否首次运行
    'host': '0.0.0.0',
    'port': 5000,
}


def load_config():
    """加载配置，文件不存在则返回默认值"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # 合并默认值，确保新字段有默认值
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config):
    """保存配置到文件"""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def hash_password(password):
    """SHA256 哈希"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def generate_password(length=12):
    """生成随机密码"""
    return secrets.token_urlsafe(length)


def is_first_run():
    """检查是否首次运行"""
    config = load_config()
    return config.get('first_run', True)


def _is_interactive():
    """检测是否为交互式终端"""
    try:
        return os.isatty(sys.stdin.fileno())
    except (OSError, AttributeError):
        return False


def _prompt(prompt_text, default=''):
    """交互式输入提示，非交互式终端自动返回默认值"""
    if not _is_interactive():
        print(prompt_text + ' (非交互式终端，使用默认值: ' + repr(default) + ')')
        return default
    print(prompt_text, end='', flush=True)
    try:
        return input().strip()
    except (EOFError, KeyboardInterrupt):
        return default


def run_setup_wizard(cli_args=None):
    """
    首次运行引导程序，交互式配置
    返回 (config, password_hash)
    """
    config = load_config()
    cli = cli_args or {}
    # 非交互式终端或 CLI 参数 → 跳过交互
    skip_interactive = bool(cli.get('password') or cli.get('debug')) or not _is_interactive()

    print()
    print('=' * 56)
    print('  欢迎使用知识点管理系统 - 首次配置向导')
    print('=' * 56)
    if skip_interactive:
        print('  非交互模式，使用默认配置')
    else:
        print('  按 Enter 使用默认值，或输入新值后按 Enter')
    print()

    # 1. 密码设置
    if cli.get('password'):
        pwd = cli['password']
        print('[1/4] 登录密码: (已通过 --password 指定)')
    elif skip_interactive:
        pwd = generate_password()
        print('[1/4] 登录密码: (自动生成) ' + pwd)
    else:
        print('[1/4] 设置登录密码')
        print('  留空自动生成随机密码，输入 "skip" 跳过密码保护')
        user_input = _prompt('  密码: ')
        if user_input.lower() == 'skip':
            pwd = ''
            config['disable_login'] = True
            print('  [OK] 已跳过密码保护，登录验证已关闭')
        elif user_input:
            pwd = user_input
            print('  [OK] 密码已设置')
        else:
            pwd = generate_password()
            print('  [OK] 已生成随机密码: ' + pwd)

    config['password_hash'] = hash_password(pwd) if pwd else ''

    # 2. 启动备份
    print()
    if cli.get('enable_startup_backup') is not None:
        enable_backup = cli['enable_startup_backup']
    elif skip_interactive:
        enable_backup = DEFAULT_CONFIG['enable_startup_backup']
    else:
        default_backup = 'Y' if DEFAULT_CONFIG['enable_startup_backup'] else 'N'
        user_input = _prompt('[2/4] 是否在每次启动时自动备份？(Y/n) [' + default_backup + ']: ', default='y')
        enable_backup = user_input.lower() != 'n'
    config['enable_startup_backup'] = enable_backup
    print('  [OK] 启动备份: ' + ('开启' if enable_backup else '关闭'))

    # 3. 调试模式
    print()
    if cli.get('debug'):
        debug_mode = True
    elif skip_interactive:
        debug_mode = DEFAULT_CONFIG['debug']
    else:
        user_input = _prompt('[3/4] 是否开启调试模式？(y/N) [N]: ', default='n')
        debug_mode = user_input.lower() == 'y'
    config['debug'] = debug_mode
    print('  [OK] 调试模式: ' + ('开启' if debug_mode else '关闭'))

    # 4. 监听地址
    print()
    if cli.get('host'):
        host = cli['host']
    elif skip_interactive:
        host = DEFAULT_CONFIG['host']
    else:
        user_input = _prompt('[4/4] 监听地址 (0.0.0.0=所有网卡) [0.0.0.0]: ', default='0.0.0.0')
        host = user_input if user_input else '0.0.0.0'
    config['host'] = host
    print('  [OK] 监听地址: ' + host)

    # 标记已完成首次配置
    config['first_run'] = False
    save_config(config)

    print()
    print('=' * 56)
    print('  配置完成！正在启动...')
    print('=' * 56)
    print()

    return config, config['password_hash']


def get_effective_config(cli_args=None):
    """
    获取合并后的有效配置（CLI 参数优先于配置文件）
    """
    config = load_config()
    cli = cli_args or {}

    # CLI 参数覆盖配置文件
    for key in ['debug', 'ssl_cert', 'ssl_key', 'host', 'port']:
        if cli.get(key):
            config[key] = cli[key]

    return config