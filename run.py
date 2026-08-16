"""知识点管理系统 - 应用入口"""
import sys
import os
import atexit
import argparse
import datetime

# 确保当前目录和 lib 目录在 path 中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'lib'))

from utils.logger import get_logger, setup_global_debug, print_banner, print_step
from utils.repair import repair_database
from services.backup_service import BackupService
from models.database import Database
from api.server import create_app
from api.auth_routes import hash_password, generate_password, set_password_hash
from utils.config import load_config, save_config, run_setup_wizard, is_first_run, get_effective_config

atexit.register(lambda: Database().close())

parser = argparse.ArgumentParser(description='知识点管理系统')
parser.add_argument('--debug', action='store_true', help='Enable debug mode')
parser.add_argument('--password', type=str, help='Set login password')
parser.add_argument('--ssl-cert', type=str, help='SSL certificate file path')
parser.add_argument('--ssl-key', type=str, help='SSL private key file path')
parser.add_argument('--generate-cert', action='store_true', help='Auto-generate self-signed certificate')
parser.add_argument('--reset-config', action='store_true', help='Reset config and re-run setup wizard')
parser.add_argument('--show-config', action='store_true', help='Show current config and exit')
parser.add_argument('--no-backup', action='store_true', help='Disable startup backup this session')
args = parser.parse_args()


def main():
    # 检测重启标记
    restart_flag = os.path.join(BASE_DIR, '.restart')
    if os.path.exists(restart_flag):
        os.remove(restart_flag)
        args.no_backup = True
        print_step('info', '备份恢复后重启，跳过启动备份')

    # --show-config：显示当前配置
    if args.show_config:
        config = load_config()
        print('当前配置 (config.json):')
        print('  debug:               ' + str(config.get('debug', False)))
        print('  enable_startup_backup: ' + str(config.get('enable_startup_backup', True)))
        print('  password_hash:       ' + ('已设置' if config.get('password_hash') else '未设置（无密码保护）'))
        print('  host:                ' + str(config.get('host', '0.0.0.0')))
        print('  port:                ' + str(config.get('port', 5000)))
        print('  first_run:           ' + str(config.get('first_run', True)))
        print('  ssl_cert:            ' + (config.get('ssl_cert') or '未设置'))
        return

    # --reset-config：重置配置
    if args.reset_config:
        config = load_config()
        config['first_run'] = True
        save_config(config)
        print_step('ok', '配置已重置')
        # 继续执行向导

    # 首次运行或重置后：启动引导程序
    if is_first_run():
        cli = {}
        if args.password:
            cli['password'] = args.password
        if args.debug:
            cli['debug'] = True
        config, password_hash = run_setup_wizard(cli)
    else:
        config = get_effective_config({
            'debug': args.debug,
            'ssl_cert': args.ssl_cert,
            'ssl_key': args.ssl_key,
        })
        password_hash = config.get('password_hash', '')

    # 保存可能被 CLI 覆盖的配置
    if args.debug:
        config['debug'] = True
        save_config(config)

    # 调试模式
    effective_debug = config.get('debug', False) or args.debug
    setup_global_debug(effective_debug)

    # 密码处理
    if not password_hash:
        if config.get('disable_login'):
            pass  # 登录验证已关闭，不需要密码
        else:
            # 使用临时文件同步密码，避免 reloader 父子进程生成不同密码
            temp_pwd_file = os.path.join(BASE_DIR, '.temp_password')
            is_child = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
            if is_child:
                # 子进程：从父进程写入的临时文件读取密码
                if os.path.exists(temp_pwd_file):
                    with open(temp_pwd_file, 'r') as f:
                        pwd = f.read().strip()
                    os.remove(temp_pwd_file)
                else:
                    pwd = args.password or generate_password()
            else:
                # 父进程：生成密码写入临时文件，不打印
                pwd = args.password or generate_password()
                with open(temp_pwd_file, 'w') as f:
                    f.write(pwd)
            if is_child:
                print('=' * 50)
                print('[SECURITY] 登录密码: ' + pwd)
                print('[SECURITY] 请妥善保管此密码（本次临时生效）')
                print('[SECURITY] 运行 --reset-config 可重新配置永久密码')
                print('=' * 50)
            password_hash = hash_password(pwd)
    else:
        if args.password:
            password_hash = hash_password(args.password)
            config['password_hash'] = password_hash
            save_config(config)

    set_password_hash(password_hash)

    # SSL 证书处理
    ssl_context = None
    if args.ssl_cert and args.ssl_key:
        ssl_context = (args.ssl_cert, args.ssl_key)
    elif args.generate_cert:
        cert_dir = os.path.join(BASE_DIR, 'certs')
        os.makedirs(cert_dir, exist_ok=True)
        cert_path = os.path.join(cert_dir, 'cert.pem')
        key_path = os.path.join(cert_dir, 'key.pem')

        import subprocess
        try:
            subprocess.run([
                'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-keyout', key_path,
                '-out', cert_path, '-days', '3650', '-nodes',
                '-subj', '/CN=knowledge-base'
            ], check=True, capture_output=True)
            print_step('ok', '自签证书已生成: ' + cert_dir)
            ssl_context = (cert_path, key_path)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print_step('warn', 'openssl 未安装，无法生成证书。请手动生成或安装 openssl。')

    # Flask debug 模式会启动 reloader 子进程，只在子进程中执行启动逻辑
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true' and os.environ.get('FLASK_RUN_FROM_CLI') != 'true':
        app = create_app(debug=effective_debug, password_hash=password_hash, ssl_context=ssl_context)
        app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=ssl_context)
        return

    print_banner()

    log = get_logger('run', debug=effective_debug)
    log.info('=' * 50)
    log.info('知识点管理系统 启动中...')

    # 密码状态提示
    if config.get('disable_login'):
        print_step('info', '登录验证已关闭，无需密码')
    elif config.get('password_hash'):
        print_step('ok', '使用已保存的密码')
    else:
        print_step('warn', '未设置密码，任何人都可访问')

    # 自修复数据库
    log.info('执行数据库自检...')
    if not repair_database():
        log.critical('数据库修复失败，无法启动')
        print_step('fail', '数据库修复失败，请检查日志')
        sys.exit(1)
    print_step('ok', '数据库初始化完成')

    # 启动时清理撤销记录
    log.info('清理过期撤销记录...')
    Database().execute_write('DELETE FROM operation_logs')
    log.info('撤销记录已清理')
    print_step('ok', '撤销记录已清理')

    # 启动时自动备份（根据配置）
    if config.get('enable_startup_backup', True) and not args.no_backup:
        try:
            log.info('执行启动备份...')
            backup = BackupService()
            result = backup.create_backup(note='启动时自动备份-' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
            log.info('启动备份完成: %s', result['filename'])
            print_step('ok', '启动备份: ' + result['filename'])
        except Exception as e:
            log.warning('启动备份失败（继续启动）: %s', str(e))
            print_step('warn', '启动备份失败: ' + str(e))
            if effective_debug:
                import traceback
                log.debug('Traceback:\n%s', traceback.format_exc())

    # 创建 Flask 应用
    app = create_app(debug=effective_debug, password_hash=password_hash, ssl_context=ssl_context)
    if ssl_context:
        print_step('ok', '应用启动: https://localhost:5000')
        log.info('HTTPS 已启用')
        log.info('应用启动: https://localhost:5000')
    else:
        print_step('ok', '应用启动: http://localhost:5000')
        log.info('应用启动: http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=ssl_context)


if __name__ == '__main__':
    main()