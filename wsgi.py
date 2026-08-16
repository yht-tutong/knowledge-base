"""Render 生产环境 WSGI 入口"""
import sys
import os
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'lib'))

from utils.logger import get_logger, print_step
from utils.repair import repair_database
from services.backup_service import BackupService
from models.database import Database
from api.server import create_app
from utils.config import load_config, save_config, run_setup_wizard, is_first_run, get_effective_config

# ---- 启动逻辑 ----
config = get_effective_config({})
password_hash = config.get('password_hash', '')

# 首次运行：自动跳过向导，生成随机密码
if is_first_run():
    config['first_run'] = False
    config['enable_startup_backup'] = False  # 云端不需要启动备份
    save_config(config)

log = get_logger('run', debug=config.get('debug', False))

# 数据库自检
if not repair_database():
    log.critical('数据库修复失败')

# 清理撤销记录
Database().execute_write('DELETE FROM operation_logs')

# 创建应用（不启用 debug，不用 reloader）
app = create_app(debug=False, password_hash=password_hash, ssl_context=None)