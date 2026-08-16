"""PythonAnywhere WSGI 配置文件
将本文件内容粘贴到 PythonAnywhere 的 WSGI configuration file 中：
    Web → 你的 Web App → Code → WSGI configuration file
"""
import sys
import os

# 项目目录（上传到 PythonAnywhere 后的路径）
# 如果目录名不同，修改下面这行
project_home = '/home/tutong/knowledge_base'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 不需要 lib 目录（PythonAnywhere 使用 pip install 安装依赖）
# 修复：移除 lib 路径，避免与系统包冲突
lib_path = os.path.join(project_home, 'lib')
if lib_path in sys.path:
    sys.path.remove(lib_path)

# ---- 启动逻辑（与 wsgi.py 一致）----
from utils.logger import get_logger
from utils.repair import repair_database
from models.database import Database
from api.server import create_app
from utils.config import load_config, save_config, is_first_run, get_effective_config

config = get_effective_config({})
password_hash = config.get('password_hash', '')

# 首次运行自动初始化
if is_first_run():
    config['first_run'] = False
    config['enable_startup_backup'] = False
    save_config(config)

# 数据库自检
repair_database()

# 清理撤销记录
Database().execute_write('DELETE FROM operation_logs')

# 创建 Flask 应用（PythonAnywhere 要求变量名为 application）
application = create_app(debug=False, password_hash=password_hash, ssl_context=None)